from django.template.defaultfilters import slugify
from django.test import TestCase
from survey.forms.locations import LocationTypeForm, LocationForm
from rapidsms.contrib.locations.models import Location, LocationType


class LocationTypeFormTest(TestCase):
    def test_valid(self):
        form_data = {'name': 'some name say country'}
        type_form = LocationTypeForm(form_data)
        type_form.is_valid()
        self.assertTrue(type_form.is_valid())

    def test_save_form(self):
        form_data = {'name': 'Test Location'}
        type_form = LocationTypeForm(form_data)
        location_type = type_form.save(commit=True)
        self.assertEqual(form_data['name'], location_type.name)
        self.assertEqual(slugify(form_data['name']), location_type.slug)
        location_type = LocationType.objects.filter(name=form_data['name'])
        self.failUnless(location_type)

    def test_name_is_required(self):
        type_form = LocationTypeForm({'name':''})
        self.assertFalse(type_form.is_valid())
        self.assertEquals(type_form.errors['name'], ['This field is required.'])

    def test_form_should_be_invalid_if_name_already_exists(self):
        a_type = LocationType.objects.create(name='type')
        type_form = LocationTypeForm({'name':a_type.name})
        self.assertFalse(type_form.is_valid())
        message = "%s already exists"% a_type.name
        self.assertEquals(type_form.errors['name'], [message])

class LocationFormTest(TestCase):
    def setUp(self):
        country = LocationType.objects.create(name='Country', slug='country')
        self.district = LocationType.objects.create(name='District', slug='district')
        self.uganda = Location.objects.create(name='Uganda', type=country)

        self.form_data = {
                            'name':'kampala',
                            'type':self.district.pk,
                            'tree_parent':self.uganda.id
                        }
    def test_valid(self):
        location_form = LocationForm(self.form_data)
        self.assertTrue(location_form.is_valid())

    def test_valid_if_editing_instance(self):
        data = self.form_data.copy()
        data['type'] = self.district
        data['tree_parent'] = self.uganda

        Location.objects.create(**data)
        location_form = LocationForm(initial=data, data=self.form_data)
        self.assertTrue(location_form.is_valid())

    def test_name_is_required(self):
        form_data = self.form_data
        form_data['name']=''
        location_form = LocationForm(form_data)
        self.assertFalse(location_form.is_valid())
        self.assertEquals(location_form.errors['name'], ['This field is required.'])

    def test_type_is_required(self):
        form_data = self.form_data
        form_data['type']=''
        location_form = LocationForm(form_data)
        self.assertFalse(location_form.is_valid())
        self.assertEquals(location_form.errors['type'], ['This field is required.'])

    def test_form_should_be_invalid_if_location_already_exists(self):
        Location.objects.create(name=self.form_data['name'], type=self.district, tree_parent=self.uganda)
        location_form = LocationForm(self.form_data)
        self.assertFalse(location_form.is_valid())
        self.assertEquals(location_form.errors['__all__'], ['This location already exists.'])

