from django.shortcuts import render
from django.http import HttpResponseRedirect
from rapidsms.contrib.locations.models import Location, LocationType
from django.contrib.auth.decorators import login_required, permission_required

from django.core.urlresolvers import reverse
from django.contrib import messages

from survey.investigator_configs import *
from survey.models.investigator import Investigator


@login_required
@permission_required('auth.can_view_batches')
def view(request):
    location_type = LocationType.objects.get(name=PRIME_LOCATION_TYPE)
    locations = Location.objects.filter(type=location_type).order_by('name')
    return render(request, 'bulk_sms/index.html', {'locations': locations})

@login_required
@permission_required('auth.can_view_batches')
def send(request):
    params = dict(request.POST)
    if valid_parameters(params, request):
        locations = Location.objects.filter(id__in=params['locations'])
        Investigator.sms_investigators_in_locations(locations=locations, text=params['text'][0])
        messages.success(request, "Your message has been sent to investigators.")
    return HttpResponseRedirect(reverse('bulk_sms'))


def valid_parameters(params, request):
    if not params.has_key('locations'):
        messages.error(request, "Please select a location.")
        return False
    if len(params['text'][0]) < 1:
        messages.error(request, "Please enter the message to send.")
        return False
    return True