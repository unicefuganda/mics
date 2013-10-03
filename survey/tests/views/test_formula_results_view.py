from datetime import date
from django.test.client import Client
from rapidsms.contrib.locations.models import Location, LocationType
from django.contrib.auth.models import User
from survey.models import HouseholdMemberGroup, GroupCondition
from survey.models.batch import Batch
from survey.models.households import HouseholdHead, Household, HouseholdMember
from survey.models.backend import Backend
from survey.models.investigator import Investigator

from survey.models.formula import *
from survey.models.question import Question, QuestionOption
from survey.views.location_widget import LocationWidget
from survey.tests.base_test import BaseTest


class NumericalFormulaResults(BaseTest):
    def setUp(self):
        self.client = Client()
        self.member_group = HouseholdMemberGroup.objects.create(name="Greater than 2 years", order=1)
        self.condition = GroupCondition.objects.create(attribute="AGE", value=2, condition="GREATER_THAN")
        self.condition.groups.add(self.member_group)

        user_without_permission = User.objects.create_user(username='useless', email='rajni@kant.com', password='I_Suck')
        raj = self.assign_permission_to(User.objects.create_user('Rajni', 'rajni@kant.com', 'I_Rock'), 'can_view_aggregates')
        self.client.login(username='Rajni', password='I_Rock')

        self.batch = Batch.objects.create(order=1)
        self.question_1 = Question.objects.create(text="Question 1?", answer_type=Question.NUMBER, order=1, group=self.member_group)
        self.question_2 = Question.objects.create(text="Question 2?", answer_type=Question.NUMBER, order=2, group=self.member_group)
        self.question_1.batches.add(self.batch)
        self.question_2.batches.add(self.batch)
        self.formula_1 = Formula.objects.create(name="Formula 1", numerator=self.question_1, denominator=self.question_2, batch=self.batch)

        district = LocationType.objects.create(name = 'District', slug = 'district')
        village = LocationType.objects.create(name = 'Village', slug = 'village')

        self.kampala = Location.objects.create(name='Kampala', type = district)
        self.village_1 = Location.objects.create(name='Village 1', type = village, tree_parent = self.kampala)
        self.village_2 = Location.objects.create(name='Village 2', type = village, tree_parent = self.kampala)

        backend = Backend.objects.create(name='something')
        investigator = Investigator.objects.create(name="Investigator 1", mobile_number="1", location=self.village_1, backend = backend, weights = 0.3)
        self.household_1 = Household.objects.create(investigator=investigator, uid=0)
        self.household_2 = Household.objects.create(investigator=investigator, uid=1)

        investigator_1 = Investigator.objects.create(name="Investigator 2", mobile_number="2", location=self.village_2, backend = backend, weights = 0.9)
        self.household_3 = Household.objects.create(investigator=investigator_1, uid=2)
        self.household_4 = Household.objects.create(investigator=investigator_1, uid=3)

        self.member1 = self.create_household_member(self.household_1)
        self.member2 = self.create_household_member(self.household_2)
        self.member3 = self.create_household_member(self.household_3)
        self.member4 = self.create_household_member(self.household_4)

        investigator.member_answered(self.question_1, self.member1, 20, self.batch)
        investigator.member_answered(self.question_2, self.member1, 200, self.batch)
        investigator.member_answered(self.question_1, self.member2, 10, self.batch)
        investigator.member_answered(self.question_2, self.member2, 100, self.batch)

        investigator_1.member_answered(self.question_1, self.member3, 40, self.batch)
        investigator_1.member_answered(self.question_2, self.member3, 400, self.batch)
        investigator_1.member_answered(self.question_1, self.member4, 50, self.batch)
        investigator_1.member_answered(self.question_2, self.member4, 500, self.batch)
        for household in Household.objects.all():
            HouseholdHead.objects.create(household=household, surname="Surname %s" % household.pk, date_of_birth='1980-09-01')

    def create_household_member(self,household):
        return HouseholdMember.objects.create(surname="Member", date_of_birth=date(1980, 2, 2), male=False,
                                              household=household)

    def test_restricted_permissions(self):
        self.assert_restricted_permission_for("/batches/%s/formulae/%s/" % (self.batch.pk, self.formula_1.pk))

    def test_get(self):
        url = "/batches/%s/formulae/%s/" % (self.batch.pk, self.formula_1.pk)
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        templates = [template.name for template in response.templates]
        self.assertIn('formula/show.html', templates)
        self.assertEquals(type(response.context['locations']), LocationWidget)

    def test_get_for_district(self):
        url = "/batches/%s/formulae/%s/?location=%s" % (self.batch.pk, self.formula_1.pk, self.kampala.pk)
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        templates = [template.name for template in response.templates]
        self.assertIn('formula/show.html', templates)
        self.assertEquals(type(response.context['locations']), LocationWidget)
        self.assertEquals(response.context['computed_value'], 6)
        self.assertEquals(len(response.context['hierarchial_data']), 2)
        self.assertEquals(response.context['hierarchial_data'][self.village_1], 3)
        self.assertEquals(response.context['hierarchial_data'][self.village_2], 9)

    def test_get_for_village(self):
        url = "/batches/%s/formulae/%s/?location=%s" % (self.batch.pk, self.formula_1.pk, self.village_1.pk)
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        templates = [template.name for template in response.templates]
        self.assertIn('formula/show.html', templates)
        self.assertEquals(type(response.context['locations']), LocationWidget)
        self.assertEquals(response.context['computed_value'], 3)
        self.assertEquals(response.context['weights'], 0.3)
        self.assertEquals(len(response.context['household_data']), 2)
        self.assertEquals(response.context['household_data'][self.household_1][self.formula_1.numerator], 20)
        self.assertEquals(response.context['household_data'][self.household_1][self.formula_1.denominator], 200)
        self.assertEquals(response.context['household_data'][self.household_2][self.formula_1.numerator], 10)
        self.assertEquals(response.context['household_data'][self.household_2][self.formula_1.denominator], 100)

class MultichoiceResults(BaseTest):
    def setUp(self):
        self.client = Client()
        self.member_group = HouseholdMemberGroup.objects.create(name="Greater than 2 years", order=1)
        self.condition = GroupCondition.objects.create(attribute="AGE", value=2, condition="GREATER_THAN")
        self.condition.groups.add(self.member_group)

        user_without_permission = User.objects.create_user(username='useless', email='rajni@kant.com', password='I_Suck')
        raj = self.assign_permission_to(User.objects.create_user('Rajni', 'rajni@kant.com', 'I_Rock'), 'can_view_aggregates')
        self.client.login(username='Rajni', password='I_Rock')

        self.batch = Batch.objects.create(order=1)
        self.question_1 = Question.objects.create(text="Question 1?", answer_type=Question.NUMBER, order=1, group=self.member_group)
        self.question_2 = Question.objects.create(text="Question 2?", answer_type=Question.NUMBER, order=2, group=self.member_group)
        self.question_3 = Question.objects.create(text="This is a question", answer_type=Question.MULTICHOICE, order=3, group=self.member_group)
        self.question_1.batches.add(self.batch)
        self.question_2.batches.add(self.batch)
        self.question_3.batches.add(self.batch)
        self.option_1 = QuestionOption.objects.create(question=self.question_3, text="OPTION 2", order=1)
        self.option_2 = QuestionOption.objects.create(question=self.question_3, text="OPTION 1", order=2)

        self.formula = Formula.objects.create(name="Name", numerator=self.question_3, denominator=self.question_1, batch=self.batch)

        district = LocationType.objects.create(name = 'District', slug = 'district')
        village = LocationType.objects.create(name = 'Village', slug = 'village')

        self.kampala = Location.objects.create(name='Kampala', type = district)
        self.village_1 = Location.objects.create(name='Village 1', type = village, tree_parent = self.kampala)
        self.village_2 = Location.objects.create(name='Village 2', type = village, tree_parent = self.kampala)

        backend = Backend.objects.create(name='something')
        investigator = Investigator.objects.create(name="Investigator 1", mobile_number="1", location=self.village_1, backend = backend, weights = 0.3)
        household_1 = Household.objects.create(investigator=investigator, uid=0)
        household_2 = Household.objects.create(investigator=investigator, uid=1)
        household_3 = Household.objects.create(investigator=investigator, uid=2)
        self.household_1 = household_1
        self.household_2 = household_2
        self.household_3 = household_3

        investigator_1 = Investigator.objects.create(name="Investigator 2", mobile_number="2", location=self.village_2, backend = backend, weights = 0.9)
        household_4 = Household.objects.create(investigator=investigator_1, uid=3)
        household_5 = Household.objects.create(investigator=investigator_1, uid=4)
        household_6 = Household.objects.create(investigator=investigator_1, uid=5)

        self.member1 = self.create_household_member(self.household_1)
        self.member2 = self.create_household_member(self.household_2)
        self.member3 = self.create_household_member(self.household_3)
        self.member4 = self.create_household_member(household_4)
        self.member5 = self.create_household_member(household_5)
        self.member6 = self.create_household_member(household_6)

        investigator.member_answered(self.question_1, self.member1, 20, self.batch)
        investigator.member_answered(self.question_3, self.member1, 1, self.batch)
        investigator.member_answered(self.question_1, self.member2, 10, self.batch)
        investigator.member_answered(self.question_3, self.member2, 1, self.batch)
        investigator.member_answered(self.question_1, self.member3, 30, self.batch)
        investigator.member_answered(self.question_3, self.member3, 2, self.batch)

        investigator_1.member_answered(self.question_1, self.member4, 30, self.batch)
        investigator_1.member_answered(self.question_3, self.member4, 2, self.batch)
        investigator_1.member_answered(self.question_1, self.member5, 20, self.batch)
        investigator_1.member_answered(self.question_3, self.member5, 2, self.batch)
        investigator_1.member_answered(self.question_1, self.member6, 40, self.batch)
        investigator_1.member_answered(self.question_3, self.member6, 1, self.batch)
        for household in Household.objects.all():
            HouseholdHead.objects.create(household=household, surname="Surname %s" % household.pk, date_of_birth='1980-09-01')


    def create_household_member(self,household):
        return HouseholdMember.objects.create(surname="Member", date_of_birth=date(1980, 2, 2), male=False,
                                              household=household)

    def test_get_for_district(self):
        url = "/batches/%s/formulae/%s/?location=%s" % (self.batch.pk, self.formula.pk, self.kampala.pk)
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        templates = [template.name for template in response.templates]
        self.assertIn('formula/show.html', templates)
        self.assertEquals(type(response.context['locations']), LocationWidget)
        self.assertEquals(response.context['computed_value'], { self.option_1.text: 27.5, self.option_2.text: 32.5})
        self.assertEquals(len(response.context['hierarchial_data']), 2)
        self.assertEquals(response.context['hierarchial_data'][self.village_1], { self.option_1.text: 15, self.option_2.text: 15})
        self.assertEquals(response.context['hierarchial_data'][self.village_2], { self.option_1.text: 40, self.option_2.text: 50})

    def test_get_for_village(self):
        url = "/batches/%s/formulae/%s/?location=%s" % (self.batch.pk, self.formula.pk, self.village_1.pk)
        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        templates = [template.name for template in response.templates]
        self.assertIn('formula/show.html', templates)
        self.assertEquals(type(response.context['locations']), LocationWidget)
        self.assertEquals(response.context['computed_value'], { self.option_1.text: 15, self.option_2.text: 15})
        self.assertEquals(response.context['weights'], 0.3)
        self.assertEquals(len(response.context['household_data']), 3)
        self.assertEquals(response.context['household_data'][self.household_1][self.formula.numerator], self.option_1)
        self.assertEquals(response.context['household_data'][self.household_1][self.formula.denominator], 20)
        self.assertEquals(response.context['household_data'][self.household_2][self.formula.numerator], self.option_1)
        self.assertEquals(response.context['household_data'][self.household_2][self.formula.denominator], 10)
        self.assertEquals(response.context['household_data'][self.household_3][self.formula.numerator], self.option_2)
        self.assertEquals(response.context['household_data'][self.household_3][self.formula.denominator], 30)
        
    def test_restricted_permissions(self):
        self.assert_restricted_permission_for("/batches/%s/formulae/%s/?location=%s" % (self.batch.pk, self.formula.pk, self.kampala.pk))
        