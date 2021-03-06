from django.test.client import Client
from django.contrib.auth.models import User
from rapidsms.contrib.locations.models import Location, LocationType
from survey.investigator_configs import PRIME_LOCATION_TYPE

from survey.tests.base_test import BaseTest


class BulkSMSTest(BaseTest):

    def setUp(self):
        self.client = Client()
        user_without_permission = User.objects.create_user(username='useless', email='rajni@kant.com', password='I_Suck')
        raj = self.assign_permission_to(User.objects.create_user('Rajni', 'rajni@kant.com', 'I_Rock'), 'can_view_batches')
        self.client.login(username='Rajni', password='I_Rock')

        district = LocationType.objects.create(name=PRIME_LOCATION_TYPE, slug='district')
        country = LocationType.objects.create(name='Country', slug = 'country')
        self.kampala = Location.objects.create(name="Kampala", type=district)
        self.abim = Location.objects.create(name="Abim", type=district)
        uganda = Location.objects.create(name="Uganda", type=country)

    def test_get(self):
        response = self.client.get('/bulk_sms')
        self.failUnlessEqual(response.status_code, 200)
        templates = [template.name for template in response.templates]
        self.assertIn('bulk_sms/index.html', templates)
        self.assertEquals(len(response.context['locations']), 2)

    def test_send(self):
        response = self.client.post('/bulk_sms/send', data={'locations': [self.kampala.pk, self.abim.pk], 'text': 'text'}, follow=True)
        self.assertEquals(len(response.context['messages']), 1)
        for message in response.context['messages']:
            self.assertEquals(str(message), "Your message has been sent to investigators.")
        self.failUnlessEqual(response.status_code, 200)
        self.assertRedirects(response, 'http://testserver/bulk_sms')

    def test_send_failures(self):
        response = self.client.post('/bulk_sms/send', data={'locations': [], 'text': 'text'}, follow=True)
        self.assertEquals(len(response.context['messages']), 1)
        for message in response.context['messages']:
            self.assertEquals(str(message), "Please select a location.")
        self.failUnlessEqual(response.status_code, 200)
        self.assertRedirects(response, 'http://testserver/bulk_sms')

        response = self.client.post('/bulk_sms/send', data={'locations': [self.kampala.pk, self.abim.pk], 'text': ''}, follow=True)
        for message in response.context['messages']:
            self.assertEquals(str(message), "Please enter the message to send.")
        self.failUnlessEqual(response.status_code, 200)
        self.assertRedirects(response, 'http://testserver/bulk_sms')

    def test_restricted_permssion(self):
        self.assert_restricted_permission_for('/bulk_sms')
        self.assert_restricted_permission_for('/bulk_sms/send')
