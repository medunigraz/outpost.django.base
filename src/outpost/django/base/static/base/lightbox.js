$(document).ready(function() {
  $('#lightbox').on('show.bs.modal', function (event) {
    var button = $(event.relatedTarget);
    var url = button.attr('href');
    var modal = $(this);
    modal.find('img').attr('src', url);
  });
});
