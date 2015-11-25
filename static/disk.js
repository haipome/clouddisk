$(document).ready(function(){
    $("#upload-btn").click(function() {
        filename = $("#upload-file").val().split('\\').pop();
        if (!filename) {
            return;
        }

        $.ajax({
            url: "/token/upload/" + filename,
            dataType: "json",
            type: "get",
            success: function (data) {
                $("#upload-key").val(data.key);
                $("#upload-token").val(data.token);
                var formdata = new FormData(document.getElementById("upload-form"));
                $.ajax({
                    url: "http://upload.qiniu.com/",
                    type: "post",
                    data: formdata,
                    enctype: 'multipart/form-data',
                    processData: false,
                    contentType: false
                }).done(function(data) {
                    alert('upload success');
                    location.reload();
                });
            }
        });
    });
});
