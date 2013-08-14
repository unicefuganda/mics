;
jQuery(function($){
  $(".chzn-select").chosen();
  $("#bulk-sms-locations").multiSelect();
});

function update_get_investigator_list_link(id){
  filter_id = ""
  if (id){
    filter_id = "filter/"+ id +"/"
  }
  $("#a-investigator-list").attr("href", "/investigators/"+ filter_id);
};

function clean_number(value){
  return value.replace(/\s+/g, '').replace(/-/g, '');
};

function strip_leading_zero(element){
  var value = $(element).val();
  if (value){
    $(element).val(value.replace(/^[0]/g,""));
    return true;
  };
};

$(function(){

  jQuery.validator.addMethod("leading_zero_if_number_is_10_digits", function(value, element) {
      return ((value.length !=10) || (value[0]==0) )
    }, "The first digit should be 0 if you enter 10 digits.");

  jQuery.validator.addMethod("no_leading_zero_if_number_is_9_digits", function(value, element) {
      return ( (value.length !=9) || (value[0] !=0))
    }, "No leading zero. Please follow format: 771234567.");

  jQuery.validator.addMethod("validate_confirm_number", function(value, element) {
        var cleaned_original = clean_number($("#investigator-mobile_number").val());
        var cleaned_confirm = clean_number(value);
        return (cleaned_original==cleaned_confirm)
      }, "Mobile number not matched.");

  $('#create-investigator-form').validate({
      ignore: ":hidden:not(select)",
      rules: {
        "name": "required",
        "mobile_number": {
          required: true,
          minlength: 9,
          no_leading_zero_if_number_is_9_digits: true,
          leading_zero_if_number_is_10_digits: true,
          remote: '/investigators/check_mobile_number'
        },
        "confirm_mobile_number":{validate_confirm_number: true, required: true},
        "age": "required",
        "surname":"required",
        "first_name":"required",
      },
      messages: {
        "age":{ number: "Please enter a valid number. No space or special charcters."},
        "mobile_number": {
          number: "Please enter a valid number. No space or special charcters.",
          minlength:jQuery.format("Too few digits. Please enter {0} digits."),
          remote: jQuery.format("{0} is already registered.")
        },
        "confirm_mobile_number":{number: "Please enter a valid number. No space or special charcters"}
      },
      errorPlacement: function(error, element) {
        if ($(element).is(':hidden')) {
          error.insertAfter(element.next());
        } else {
          error.insertAfter(element);
        };
       },
      submitHandler: function(form){
         strip_leading_zero("#investigator-mobile_number");
         strip_leading_zero("#investigator-confirm_mobile_number");
         var button = $(form).find('button'),
             value = button.val();
         button.attr('disabled', true);
         form.submit();
       }
  });

  $("input.small-positive-number").each(function(){
      $(this).rules('add', {required:true, min:0, max:10});
  });

  $("#investigator-confirm_mobile_number").on('paste', function(e) {
    e.preventDefault();
  });

  $('input[name=location]').on('change', function(){
      update_get_investigator_list_link($(this).val());
  });

});