(function(factory) {
  if (typeof define === 'function' && define.amd) {
    // AMD. Register as an anonymous module.
    define(['jquery'], factory);
  } else if (typeof exports === 'object') {
    // Node/CommonJS
    module.exports = factory(require('jquery'));
  } else {
    // Browser globals
    factory(jQuery);
  }
}(function($) {

  $.views.delimiters('[[', ']]');

  $.fn.confirm = function(title, content, proceed) {
    var popover = {
      title: title,
      content: content,
      html: true,
      trigger: 'focus'
    };
    this.each(function() {
      $(this).popover(popover).on('inserted.bs.popover', function() {
        $($(this).data('bs.popover').$tip).find('.proceed').on('click', proceed);
      });
    });
  };

  var $originalAjax = $.ajax.bind($);

  $.ajax = function (url, options) {
    if (typeof url === 'object') {
      options = url;
      url = undefined;
    }
    options = options || {};

    // Instantiate our own.
    var xmlHttpReq;

    if (!options.xhr) {
      xmlHttpReq = $.ajaxSettings.xhr();
    } else {
      xmlHttpReq = options.xhr();
    }

    // Make it use our own.
    options.xhr = function () {
      return xmlHttpReq;
    };

    var chunking = options.chunking || $.ajaxSettings.chunking;

    // this line looks strange, but without it chrome doesn't catch `progress` event on uploading. Seems like engine bug
    xmlHttpReq.upload.onprogress = null;

    var $newPromise = $originalAjax(url, options);

    // Extend our own.
    $newPromise.progress = function (handler) {
      // Download progress
      var lastChunkLen = 0;
      xmlHttpReq.addEventListener('progress', function (e) {
        var params = [e],
          chunk = '';

        if (this.readyState == 3 && chunking) {
          chunk = this.responseText.substr(lastChunkLen);
          lastChunkLen = this.responseText.length;
          params.push(chunk);
        }
        handler.apply(this, params);
      }, false);

      return this;
    };

    $newPromise.uploadProgress = function(handler) {
      // Upload progress
      if (xmlHttpReq.upload) {
        xmlHttpReq.upload.addEventListener('progress', function (e) {
          handler.apply(this, [e]);
        }, false);
      }

      return this;
    };

    return $newPromise;
  };
}));
$(document).ready(function() {
  var csrftoken = $.cookie('csrftoken');
  function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
  }
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
      if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
        xhr.setRequestHeader('X-CSRFToken', csrftoken);
      }
    }
  });
});
