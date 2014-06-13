$(document).ready(function() {
	// fade table rows
	$('tr.reminderRow').mouseenter(function(){
		$buttons = $(this).find('div');
		$.each($buttons, function(index, button) {
			if ($(button).is(':visible')) {
				$(button).fadeTo(50,1);
			}
		});
	});
	$('tr.reminderRow').mouseleave(function(){
		$buttons = $(this).find('div');
		$.each($buttons, function(index, button) {
			if ($(button).is(':visible')) {
				$(button).fadeTo(50,.25);
			}
		});
	});

	// allow editing of reminders
	$('div.editbutton').click(function() {
		// $(this).after('<br>');
		$(this).parent().find('form').show();
		$(this).hide();
	});

	// submit form
	$('div.submitbutton').click(function(){
		$(this).parent().submit()
	})

	// edit reminders
	var request;
	$('form.updateForm').submit(function(event) {
		if (request) {
			request.abort();
		}

		var $form = $(this);
		var $inputs = $form.find("input");
		var serializedData = $form.serialize();

		// disable input fields
		$inputs.prop("disabled", true);

		// make request
		var request = $.ajax({
			url: "/updateReminder",
			type: "post",
			data: serializedData
		});

		request.done(function(response, textStatus, jqXHR) {
			$form.parent().find("span").text(response);
			$form.hide();
			$form.parent().find("div.editbutton").show();
		});

		request.fail(function(jqXHR, textStatus, errorThrown) {
			alert("Failed to update your reminder!");
		});

		request.always(function(){
			$inputs.prop("disabled", false);
		});

		// prevent default posting
		event.preventDefault();
	});

	// delete reminders
	$('div.deletebutton').click(function() {
		var key = $(this).attr('key');
		$.post("/deleteReminder", 
			{'key': key}, 
			function(data) {
				if (data == 'Success') {
					$('tr#'+key).fadeOut('fast');
					};
				}, 
			"text");
	});

});	