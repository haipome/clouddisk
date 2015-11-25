#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import time
import qiniu
import logging

from flask import Flask
from flask import g, request, session, url_for, abort, redirect, flash, current_app, render_template, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug import generate_password_hash, check_password_hash
from logging.handlers import RotatingFileHandler
from functools import update_wrapper

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
@app.route("/token/upload/<filename>")
def token_upload(filename):
    key = g.user.account.encode('utf8') + '/' + filename.encode('utf8')
    token = qn.upload_token(qiniu_bucket, key)
    return jsonify({'key': key, 'token': token})

@app.route("/disk/")
@app.route("/disk/<path:prefix>")
@require_login
def disk(prefix=None):
    bucket = BucketManager(qn)
    marker = None
    while True:
        ret, eof, info = bucket.list(qiniu_bucket, prefix=prefix, marker=marker, limit=1000)
    return render_template('disk.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0")

