#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import qiniu
import time
import datetime
import urllib
import urlparse
import logging

from flask import Flask
from flask import g, request, session, url_for, abort, redirect, flash, current_app, render_template, jsonify, current_app
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug import generate_password_hash, check_password_hash
from logging.handlers import RotatingFileHandler
from functools import update_wrapper
from qiniu import build_batch_delete

qiniu_bucket = 'disk'
qiniu_access_key = '1qtawbAy3V6EKPpVX3an_8DuSWRPz3A-0_BuU3zI'
qiniu_secret_key = 'XSTQxmV7kRjy5oru0Ie7XUK0Aj2myIAkNurT3M0n'
qn = qiniu.Auth(qiniu_access_key, qiniu_secret_key)

app = Flask(__name__)

app.config['SECRET_KEY'] = '\xc444\xc3\x9f\x83\xe6p\x83N\x7fZ\x1cW\x01\x11\xe8a\xd7%=\xc9\xe5p'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/qiniu_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

def init_log(app):
    app.logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[%(asctime)s] (%(levelname)s):%(filename)s:%(funcName)s:%(lineno)d: %(message)s')
    debug_log = os.path.join(app.root_path, 'log/debug.log')
    debug_log_handler = RotatingFileHandler(debug_log, maxBytes=10000000, backupCount=5)
    debug_log_handler.setLevel(logging.DEBUG)
    debug_log_handler.setFormatter(formatter)
    app.logger.addHandler(debug_log_handler)

init_log(app)
db = SQLAlchemy(app)

def current_timestamp():
    return int(time.time())

class User(db.Model):
    __tablename__   = 'users'
    __table_args__  = {'mysql_engine':'InnoDB', 'mysql_charset':'utf8'}

    id              = db.Column(db.Integer, db.Sequence('user_id_seq'), primary_key=True)
    regist_time     = db.Column(db.Integer, default=current_timestamp)
    account         = db.Column(db.String(30), unique=True)
    password_hash   = db.Column(db.String(80))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


def require_login(f):
    def page_protected(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return update_wrapper(page_protected, f)

def is_valid_account(account):
    if not re.match('^\w{2,30}$', account):
        return False
    return True

def human_size(size):
    for unit in ['B','KB','MB']:
        if abs(size) < 1000.0:
            return "%3.3f%s" % (size, unit)
        size /= 1000.0
    return "%.3f%s" % (size, 'GB')

@app.before_request
def setup_user():
    g.user = None
    user_id = session.get('user_id', None)
    if user_id:
        g.user = User.query.get(user_id)

@app.route("/")
def index():
    if not g.user:
        return render_template('index.html')
    return redirect(url_for('disk'))

@app.route("/regist/", methods=['POST'])
def regist():
    account = request.form.get("account")
    password = request.form.get("password")
    if not account or not password:
        return redirect(url_for('index'))
    if not is_valid_account(account):
        flash("account is invalid")
        return redirect(url_for('index'))
    user = User.query.filter(User.account == account).first()
    if user:
        flash("account already exist")
        return redirect(url_for('index'))
    user = User()
    user.account = account
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    return redirect(url_for('disk'))

@app.route("/login/", methods=['POST'])
def login():
    account = request.form.get("account")
    password = request.form.get("password")
    if not account or not password:
        return redirect(url_for('index'))
    user = User.query.filter(User.account == account).first()
    if not user:
        flash("account not exist")
        return redirect(url_for('index'))
    if not user.check_password(password):
        flash("password not correct")
        return redirect(url_for('index'))
    session['user_id'] = user.id
    return redirect(url_for('disk'))

@app.route("/logout/")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@require_login
@app.route("/token/upload/<path:filename>")
def token_upload(filename):
    key = (g.user.account + '/' + filename).encode('utf8')
    token = qn.upload_token(qiniu_bucket, key)
    return jsonify({'key': key, 'token': token})

@app.route("/disk/")
@app.route("/disk/<path:prefix>")
@require_login
def disk(prefix=None):
    if prefix:
        if prefix[-1] != '/':
            prefix = prefix + '/'
    else:
        prefix = ''
    real_prefix = g.user.account + '/' + prefix

    parents = []
    parents.append({'name': 'Home', 'url': url_for('disk')})
    current_path = ''
    for folder in prefix.split('/')[:-1]:
        if folder:
            parents.append({'name': folder, 'url': url_for('disk') + current_path + folder + '/'})
        current_path = current_path + folder + '/'

    bucket = qiniu.BucketManager(qn)
    marker = None

    items = []
    folders = []
    while True:
        ret, eof, _ = bucket.list(qiniu_bucket, prefix=real_prefix, marker=marker, limit=1000)
        for item in ret['items']:
            name = item['key'][len(real_prefix):]
            if not name:
                continue
            if '/' in name:
                folder = name.split('/')[0]
                if folder and folder not in folders:
                    folders.append(folder)
            else:
                items.append({'key': item['key'][len(g.user.account):], 'name': name,
                    'modified': datetime.datetime.fromtimestamp(int(item['putTime'] / 1e7)).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': human_size(item['fsize'])})
        if eof:
            break
        marker = ret['marker']
    folders.sort()
    items.sort(key=lambda item: item['name'])

    return render_template('disk.html', prefix=prefix, parents=parents, folders=folders, items=items)

@app.route("/new_folder/", methods=['POST'])
@require_login
def new_folder():
    name = request.form.get('name', '')
    if not name:
        return jsonify({'result': 'fail'})
    key = (g.user.account + '/' + name).encode('utf8')
    if key[-1] != '/':
        key += '/'
    token = qn.upload_token(qiniu_bucket)
    ret, info = qiniu.put_data(token, key.decode('utf8'), 'folder')
    if not ret:
        return jsonify({'result': 'fail'})
    return jsonify({'result': 'success'})

@app.route("/delete/", methods=['POST'])
@require_login
def delete():
    key = request.form.get('key', '')
    if not key:
        return jsonify({'result': 'fail'})
    real_key = (g.user.account + key).encode('utf8')
    bucket = qiniu.BucketManager(qn)
    if real_key[-1] != '/':
        ret, info = bucket.delete(qiniu_bucket, real_key)
        if ret:
            return jsonify({'result': 'fail'})
    else:
        items = []
        marker = None
        while True:
            ret, eof, _ = bucket.list(qiniu_bucket, prefix=real_key, marker=marker, limit=1000)
            for item in ret['items']:
                items.append(item['key'].encode('utf8'))
            if eof:
                break
            marker = ret['marker']
        ops = build_batch_delete(qiniu_bucket, items)
        ret, info = bucket.batch(ops)
        if ret[0]['code'] != 200:
            return jsonify({'result': 'fail'})
    return jsonify({'result': 'success'})

@app.route("/download/")
@require_login
def download():
    key = request.args.get('key', '')
    if not key:
        return jsonify({'errormsg': 'invalid argument'})
    real_name = key.split('/')[-1]
    real_key = g.user.account + key
    domain = "7xon9u.com1.z0.glb.clouddn.com"
    base_url = 'http://%s/%s?attname=%s' % (domain, urllib.pathname2url(real_key.encode('utf8')), urllib.pathname2url(real_name.encode('utf8')))
    download_url = qn.private_download_url(base_url, expires=3600)
    return redirect(download_url)

if __name__ == '__main__':
    app.run(host="0.0.0.0")

