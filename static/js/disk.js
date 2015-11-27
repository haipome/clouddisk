$(document).ready(function(){
    $("#upload-file-button").click(function() {
        var button = $(this);
        var prefix = button.attr("prefix");
        var filename = $("#upload-file-name").val().split('\\').pop();
        if (!filename) {
            return;
        }

        $.ajax({
            url: "/token/upload/" + prefix + filename,
            dataType: "json",
            type: "get",
            success: function (data) {
                var formdata = new FormData(document.getElementById("upload-file-form"));
                formdata.append("key", data.key);
                formdata.append("token", data.token);
                button.button("loading");
                $.ajax({
                    url: "http://upload.qiniu.com/",
                    type: "post",
                    data: formdata,
                    contentType: false,
                    processData: false,
                    enctype: "multipart/form-data",
                    dataType: "json",
                    success: function(data) {
                        if (data.error) {
                            alert("Upload fail: " + data.error);
                            button.button("reset");
                        } else {
                            button.html("Upload success");
                            setTimeout(function(){location.reload();}, 1000);
                        }
                    }
                });
            }
        });
    });

    $("#new-folder-button").click(function() {
        var button = $(this);
        var prefix = button.attr("prefix");
        var name = $("#new-folder-name").val();
        if (!name) {
            return;
        }

        button.button("loading");
        $.ajax({
            url: "/new_folder/",
            type: "post",
            data: { name: prefix + name },
            dataType: "json",
            success: function(data) {
                if (data.result == 'success') {
                    button.html("Create success");
                    setTimeout(function(){location.reload();}, 1000);
                } else {
                    alert("Create folder fail");
                    button.button("reset");
                }
            }
        });
    });

    $(".oper-delete").click(function() {
        var button = $(this);
        var name = button.closest("tr").find(".item-name").first().html();
        if (confirm("Delete file " + name + "?")) {
            var key = button.closest("tr").attr("key");
            $.ajax({
                url: "/delete/",
                type: "post",
                data: { key: key },
                dataType: "json",
                success: function(data) {
                    if (data.result == 'success') {
                        button.closest("tr").remove();
                    }
                }
            });
        }
    });
});

