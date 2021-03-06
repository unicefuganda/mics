from datetime import date, datetime, timedelta

from django.test import TestCase
from mock import patch
from django.db import IntegrityError, DatabaseError
from rapidsms.contrib.locations.models import Location, LocationType
from django.template.defaultfilters import slugify
from survey.models import AnswerRule, HouseholdHead, BatchQuestionOrder, LocationCode, EnumerationArea, LocationTypeDetails

from survey.models.batch import Batch
from survey.investigator_configs import COUNTRY_PHONE_CODE
from survey.models.household_batch_completion import HouseholdMemberBatchCompletion
from survey.models.backend import Backend
from survey.models.households import Household, HouseholdMember
from survey.models.investigator import Investigator
from survey.models.question import Question, NumericalAnswer
from survey.models.householdgroups import HouseholdMemberGroup, GroupCondition
from survey.models.surveys import Survey


class InvestigatorTest(TestCase):
    def setUp(self):
        self.member_group = HouseholdMemberGroup.objects.create(name="Greater than 2 years", order=1)
        self.condition = GroupCondition.objects.create(attribute="AGE", value=2, condition="GREATER_THAN")
        self.condition.groups.add(self.member_group)
        self.survey = Survey.objects.create(name="haha")
        self.backend = Backend.objects.create(name='something')
        self.kampala = Location.objects.create(name="Kampala")
        self.ea = EnumerationArea.objects.create(name="EA1", survey=self.survey)
        self.ea.locations.add(self.kampala)

        self.investigator = Investigator.objects.create(name="", mobile_number="123456789",
                                                        ea=self.ea,
                                                        backend=self.backend)

        self.household = Household.objects.create(investigator=self.investigator,
                                                  ea=self.investigator.ea, uid=0)

        self.household_member = HouseholdMember.objects.create(surname="Member",
                                                               date_of_birth=date(1980, 2, 2), male=False,
                                                               household=self.household)

    def test_fields(self):
        investigator = Investigator()
        fields = [str(item.attname) for item in investigator._meta.fields]
        self.assertEqual(len(fields), 13)
        for field in ['id', 'name', 'mobile_number', 'created', 'modified', 'male', 'age', 'level_of_education',
                      'ea_id', 'language', 'backend_id', 'weights', 'is_blocked']:
            self.assertIn(field, fields)

    def test_store(self):
        investigator = Investigator.objects.create(name="Investigator", mobile_number="987654321",
                                                   ea=self.ea,
                                                   backend=self.backend, weights=30.99)
        self.failUnless(investigator.id)
        self.failUnless(investigator.created)
        self.failUnless(investigator.modified)
        self.assertEqual(investigator.identity, COUNTRY_PHONE_CODE + investigator.mobile_number)
        self.assertEqual(investigator.weights, 30.99)

    def test_mobile_number_is_unique(self):
        self.failUnlessRaises(IntegrityError, Investigator.objects.create, mobile_number="123456789")

    def test_mobile_number_length_must_be_less_than_10(self):
        mobile_number_of_length_11 = "01234567891"
        self.failUnlessRaises(DatabaseError, Investigator.objects.create, mobile_number=mobile_number_of_length_11)

    def test_location_hierarchy(self):
        country = LocationType.objects.create(name="Country", slug=slugify("country"))
        city = LocationType.objects.create(name="City", slug=slugify("city"))
        uganda = Location.objects.create(name="Uganda", type=country)
        kampala = Location.objects.create(name="Kampala", type=city, tree_parent=uganda)
        ea = EnumerationArea.objects.create(name="EA1", survey=self.survey)
        ea.locations.add(kampala)
        investigator = Investigator.objects.create(name="investigator name", mobile_number="9876543210",
                                                   ea=ea, backend=self.backend)
        ea.locations.add(kampala)
        self.assertEquals(investigator.location_hierarchy(), {'Country': uganda, 'City': kampala})

    def test_locations_in_hierarchy(self):
        country = LocationType.objects.create(name="Country", slug=slugify("country"))
        city = LocationType.objects.create(name="City", slug=slugify("city"))
        uganda = Location.objects.create(name="Uganda", type=country)
        kampala = Location.objects.create(name="Kampala", type=city, tree_parent=uganda)
        ea = EnumerationArea.objects.create(name="EA1", survey=self.survey)
        ea.locations.add(kampala)
        investigator = Investigator.objects.create(name="investigator name", mobile_number="9876543210",
                                                   ea=ea, backend=self.backend)
        location_hierarchy = investigator.locations_in_hierarchy()
        self.assertEqual(2, len(location_hierarchy))
        self.assertIn(kampala, location_hierarchy)
        self.assertIn(uganda, location_hierarchy)

    def test_saves_household_member_answer_and_batch_is_complete(self):
        household_member1 = HouseholdMember.objects.create(household=self.household, surname="abcd", male=True,
                                                           date_of_birth=date(1989, 2, 2))
        batch = Batch.objects.create(order=1)
        batch.open_for_location(self.investigator.location)
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_1.batches.add(batch)
        BatchQuestionOrder.objects.create(batch=batch, question=question_1, order=1)

        self.investigator.member_answered(question_1, household_member1, answer=34, batch=batch)
        completed_batches = HouseholdMemberBatchCompletion.objects.filter()

        self.assertEqual(self.investigator.last_answered_question(), question_1)
        self.assertEqual(len(completed_batches), 1)
        self.assertEqual(completed_batches[0].householdmember, household_member1)

    def test_saves_household_member_answer_and_batch_is_not_complete_if_more_questions_exists(self):
        household_member1 = HouseholdMember.objects.create(household=self.household, surname="abcd", male=True,
                                                           date_of_birth=date(1989, 2, 2))
        batch = Batch.objects.create(order=1)
        batch.open_for_location(self.investigator.location)
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)

        question_2 = Question.objects.create(text="How many women are there in this household?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)
        question_1.batches.add(batch)
        question_2.batches.add(batch)

        BatchQuestionOrder.objects.create(batch=batch, question=question_1, order=1)
        BatchQuestionOrder.objects.create(batch=batch, question=question_2, order=2)

        self.investigator.member_answered(question_1, household_member1, answer=34, batch=batch)
        completed_batches = HouseholdMemberBatchCompletion.objects.filter()

        self.assertEqual(self.investigator.last_answered_question(), question_1)
        self.assertEqual(len(completed_batches), 0)
        self.assertEqual(household_member1.next_question(question_1, batch), question_2)

    def test_knows_next_question_for_household_member_based_on_answer_rule(self):
        self.batch = Batch.objects.create(name="BATCH", order=1)
        self.batch.open_for_location(self.investigator.location)
        question_1 = Question.objects.create(identifier="identifier1",
                                             text="Question 1", answer_type='number',
                                             order=1, subquestion=False, group=self.member_group)

        question_2 = Question.objects.create(identifier="identifier2",
                                             text="Question 2", answer_type='number',
                                             order=2, subquestion=False, group=self.member_group)
        question_3 = Question.objects.create(identifier="identifier3",
                                             text="Question 3", answer_type='number',
                                             order=3, subquestion=False, group=self.member_group)
        order = 1
        for question in [question_1, question_2, question_3]:
            self.batch.questions.add(question)
            BatchQuestionOrder.objects.create(batch=self.batch, question=question, order=order)
            order += 1

        AnswerRule.objects.create(question=question_1, action=AnswerRule.ACTIONS['SKIP_TO'],
                                  condition=AnswerRule.CONDITIONS['EQUALS'], validate_with_value=1,
                                  next_question=question_3)

        next_question = self.investigator.member_answered(question_1, self.household_member, answer=1, batch=self.batch)
        self.assertNotEqual(question_2, next_question)
        self.assertEqual(question_3, next_question)

    def test_knows_next_question_for_household_member_from_batch_to_batch(self):
        batch = Batch.objects.create(name="BATCH", order=1)
        batch2 = Batch.objects.create(name="BATCH", order=2)
        batch.open_for_location(self.investigator.location)
        batch2.open_for_location(self.investigator.location)
        question_1 = Question.objects.create(identifier="identifier1",
                                             text="Question 1", answer_type='number',
                                             order=1, subquestion=False, group=self.member_group)

        question_2 = Question.objects.create(identifier="identifier2",
                                             text="Question 2", answer_type='number',
                                             order=2, subquestion=False, group=self.member_group)
        question_3 = Question.objects.create(identifier="identifier3",
                                             text="Question 3", answer_type='number',
                                             order=3, subquestion=False, group=self.member_group)

        order = 1
        for question in [question_1, question_2]:
            batch.questions.add(question)
            BatchQuestionOrder.objects.create(batch=batch, question=question, order=order)
            order += 1

        batch2.questions.add(question_3)
        BatchQuestionOrder.objects.create(batch=batch2, question=question_3, order=1)

        next_question = self.investigator.member_answered(question_2, self.household_member, answer=1, batch=batch)
        self.assertEqual(question_3, next_question)

    def test_knows_next_question_for_household_member_when_switching_batches(self):
        batch = Batch.objects.create(name="BATCH", order=1)
        batch2 = Batch.objects.create(name="BATCH", order=2)
        batch.open_for_location(self.investigator.location)
        batch2.open_for_location(self.investigator.location)
        question_1 = Question.objects.create(identifier="identifier1",
                                             text="Question 1", answer_type='number',
                                             order=1, subquestion=False, group=self.member_group)

        question_2 = Question.objects.create(identifier="identifier2",
                                             text="Question 2", answer_type='number',
                                             order=2, subquestion=False, group=self.member_group)
        question_3 = Question.objects.create(identifier="identifier3",
                                             text="Question 3", answer_type='number',
                                             order=3, subquestion=False, group=self.member_group)
        question_4 = Question.objects.create(identifier="identifier4",
                                             text="Question 4", answer_type='number',
                                             order=4, subquestion=False, group=self.member_group)
        question_5 = Question.objects.create(identifier="identifier5",
                                             text="Question 5", answer_type='number',
                                             order=5, subquestion=False, group=self.member_group)
        order = 1
        for question in [question_1, question_2, question_3]:
            batch.questions.add(question)
            BatchQuestionOrder.objects.create(batch=batch, question=question, order=order)
            order += 1

        batch2.questions.add(question_4)
        batch2.questions.add(question_5)

        BatchQuestionOrder.objects.create(batch=batch2, question=question_4, order=1)
        BatchQuestionOrder.objects.create(batch=batch2, question=question_5, order=2)

        next_question = self.investigator.member_answered(question_1, self.household_member, answer=1, batch=batch)
        self.assertEqual(question_2, next_question)

        batch.close_for_location(self.investigator.location)
        next_question = self.investigator.member_answered(question_4, self.household_member, answer=1, batch=batch2)
        self.assertEqual(question_5, next_question)

    def test_should_know_how_to_remove_all_households_that_do_not_belong_to_investigators_location(self):
        entebbe = Location.objects.create(name="Entebbe")
        ea = EnumerationArea.objects.create(name="EA2", survey=self.survey)
        ea.locations.add(entebbe)
        self.investigator.ea = ea
        self.investigator.save()

        self.investigator.remove_invalid_households()

        updated_household = Household.objects.get(id=self.household.id)
        self.assertEqual(0, len(self.investigator.households.all()))
        self.assertIsNone(updated_household.investigator)

    def test_knows_first_open_batch(self):
        batch_1 = Batch.objects.create(name="Batch 1", order=1)
        batch_2 = Batch.objects.create(name="Batch 2", order=2)
        batch_3 = Batch.objects.create(name="Batch 3", order=3)

        batch_3.open_for_location(self.investigator.location)
        batch_1.open_for_location(self.investigator.location)
        batch_2.open_for_location(self.investigator.location)

        self.assertEqual(batch_1, self.investigator.first_open_batch())

    def test_knows_when_last_registered_member(self):
        masaka = Location.objects.create(name="Masaka")
        investigator = Investigator.objects.create(name="Another investigator",
                                                   mobile_number='779432679',
                                                   ea=self.ea,
                                                   backend=self.backend)
        household = Household.objects.create(investigator=investigator, location=investigator.location,
                                             uid='10')

        HouseholdHead.objects.create(household=household, surname="head_registered",
                                     date_of_birth=datetime(1980, 02, 02), male=False)
        latest_member = HouseholdMember.objects.create(household=household, surname="new member",
                                                       date_of_birth=datetime(2002, 02, 02), male=False)
        self.assertEqual(latest_member, investigator.last_registered())

    def test_knows_last_registered_member_is_None_if_no_member_has_been_created_for_investigator_household(self):
        masaka = Location.objects.create(name="Masaka")
        investigator = Investigator.objects.create(name="Another investigator",
                                                   mobile_number='779432679',
                                                   ea=self.ea,
                                                   backend=self.backend)
        household = Household.objects.create(investigator=investigator, location=investigator.location,
                                             uid='10')

        self.assertIsNone(investigator.last_registered())

    def test_knows_member_was_registered_within_time_out_minutes(self):
        masaka = Location.objects.create(name="Masaka")
        TIMEOUT_MINUTES = 5
        investigator = Investigator.objects.create(name="Another investigator",
                                                   mobile_number='779432679',
                                                   ea=self.ea,
                                                   backend=self.backend)
        household = Household.objects.create(investigator=investigator, location=investigator.location,
                                             uid='10')

        HouseholdHead.objects.create(household=household, surname="head_registered",
                                     date_of_birth=datetime(1980, 02, 02), male=False)
        HouseholdMember.objects.create(household=household, surname="new member",
                                       date_of_birth=datetime(2002, 02, 02), male=False)

        self.assertTrue(investigator.created_member_within(TIMEOUT_MINUTES))

    def test_knows_member_was_registered_within_time_out_minutes_but_in_different_survey_which_is_not_open(self):
        masaka = Location.objects.create(name="Masaka")
        TIMEOUT_MINUTES = 5
        investigator = Investigator.objects.create(name="Another investigator",
                                                   mobile_number='779432679',
                                                   ea=self.ea,
                                                   backend=self.backend)
        open_survey = Survey.objects.create(name="open survey", description="open survey", has_sampling=True)
        closed_survey = Survey.objects.create(name="open survey", description="open survey", has_sampling=True)

        household = Household.objects.create(investigator=investigator, location=investigator.location,
                                             uid='10', survey=closed_survey)

        HouseholdHead.objects.create(household=household, surname="head_registered",
                                     date_of_birth=datetime(1980, 02, 02), male=False)
        HouseholdMember.objects.create(household=household, surname="new member",
                                       date_of_birth=datetime(2002, 02, 02), male=False)
        with patch.object(Survey, "currently_open_survey", return_value=open_survey):
            self.assertFalse(investigator.created_member_within(TIMEOUT_MINUTES, open_survey))

    def test_knows_last_member_was_registered_after_time_out_minutes(self):
        masaka = Location.objects.create(name="Masaka")
        TIMEOUT_MINUTES = 5
        investigator = Investigator.objects.create(name="Another investigator",
                                                   mobile_number='779432679',
                                                   ea=self.ea,
                                                   backend=self.backend)
        household = Household.objects.create(investigator=investigator, location=investigator.location,
                                             uid='10')

        household_head = HouseholdHead.objects.create(household=household, surname="head_registered",
                                                      date_of_birth=datetime(1980, 02, 02), male=False)
        household_member = HouseholdMember.objects.create(household=household, surname="new member",
                                                          date_of_birth=datetime(2002, 02, 02), male=False)

        household_head.created -= timedelta(minutes=(TIMEOUT_MINUTES + 2), seconds=1)
        household_head.save()

        household_member.created -= timedelta(minutes=(TIMEOUT_MINUTES + 2), seconds=1)
        household_member.save()

        self.assertFalse(investigator.created_member_within(TIMEOUT_MINUTES))

    def test_knows_member_was_registered_within_time_out_minutes_is_false_if_no_member_exists(self):
        masaka = Location.objects.create(name="Masaka")
        TIMEOUT_MINUTES = 5
        investigator = Investigator.objects.create(name="Another investigator",
                                                   mobile_number='779432679',
                                                   ea=self.ea,
                                                   backend=self.backend)
        household = Household.objects.create(investigator=investigator, location=investigator.location,
                                             uid='10')

        self.assertFalse(investigator.created_member_within(TIMEOUT_MINUTES))

    def test_investigator_knows_non_response_reporting_is_activated_for_his_location_if_there_are_HH_who_qualify(self):
        batch = Batch.objects.create(name="hoho")

        household_head = HouseholdHead.objects.create(surname="head", date_of_birth=date(1980, 2, 4), male=False,
                                                      household=self.household)
        self.investigator.batch_completion_completed_households.all().delete()

        batch.open_for_location(self.kampala)
        batch.activate_non_response_for(self.kampala)

        self.assertTrue(self.investigator.can_report_non_response())

    def test_investigator_knows_non_response_reporting_is_deactivated_for_his_location(self):
        batch = Batch.objects.create(name="hoho")

        batch.open_for_location(self.kampala)
        batch.deactivate_non_response_for(self.kampala)

        self.assertFalse(self.investigator.can_report_non_response())

    def test_investigator_knows_non_response_reporting_is_also_deactivated_for_his_location_if_there_are_no_HH_who_qualify(
            self):
        batch = Batch.objects.create(name="hoho")
        self.household.batch_completed(batch)

        self.assertFalse(self.investigator.can_report_non_response())

    def test_investigator_knows_its_location_from_its_ea(self):
        self.assertEqual(self.kampala, self.investigator.location)

    def test_returns_none_if_its_ea_has_no_location(self):
        ea = EnumerationArea.objects.create(name="EA2", survey=self.survey)
        investigator = Investigator.objects.create(name="investigator name_1", mobile_number="9876543210", backend=self.backend, ea=ea)
        self.assertEqual(None, investigator.location)

    def test_location_property(self):
        self.assertEqual(self.kampala, self.investigator.location)

class InvestigatorGenerateReport(TestCase):
    def setUp(self):
        country = LocationType.objects.create(name="Country", slug=slugify("country"))
        district = LocationType.objects.create(name="District", slug=slugify("district"))
        city = LocationType.objects.create(name="City", slug=slugify("city"))
        uganda = Location.objects.create(name="Uganda", type=country)
        self.abim = Location.objects.create(name="Abim", type=district, tree_parent=uganda)
        kampala = Location.objects.create(name="Kampala", type=city, tree_parent=self.abim)
        some_city = Location.objects.create(name="SomeCity", type=city, tree_parent=self.abim)

        self.backend = Backend.objects.create(name='something')
        self.survey = Survey.objects.create(name='SurveyA')

        self.ea = EnumerationArea.objects.create(name="EA1", survey=self.survey)
        self.ea_2 = EnumerationArea.objects.create(name="EA2", survey=self.survey)
        self.ea.locations.add(kampala)
        self.ea_2.locations.add(some_city)
        self.batch = Batch.objects.create(order=1, name='somebatch', survey=self.survey)
        self.batch.open_for_location(self.abim)

        self.investigator_1 = Investigator.objects.create(name="investigator name_1", mobile_number="9876543210",
                                                          ea=self.ea, backend=self.backend)
        self.household_1 = Household.objects.create(investigator=self.investigator_1, ea=self.investigator_1.ea,
                                                    survey=self.survey)
        self.household_2 = Household.objects.create(investigator=self.investigator_1, ea=self.investigator_1.ea,
                                                    survey=self.survey)

        self.investigator_2 = Investigator.objects.create(name="investigator name_2", mobile_number="9876543211",
                                                          ea=self.ea_2, backend=self.backend)

    def test_should_return_headers_when_generate_report_called(self):
        Investigator.objects.all().delete()
        data = ['Investigator', 'Phone Number']
        data.extend(LocationType.objects.all().values_list('name', flat=True))

        response = Investigator.generate_completion_report(self.survey)
        self.assertIn(data, response)

    def test_should_return_data_when_generate_data_called(self):
        data = [self.investigator_1.name, self.investigator_1.mobile_number]
        data.extend([loc.name for loc in self.investigator_1.location_hierarchy().values()])
        response = Investigator.generate_completion_report(self.survey)
        self.assertIn(data, response)

    def test_should_know_if_investigator_has_completed_survey(self):
        member_group = HouseholdMemberGroup.objects.create(name='group1', order=1)
        question = Question.objects.create(text="some question", answer_type=Question.NUMBER, order=1,
                                           group=member_group)
        self.batch.questions.add(question)
        BatchQuestionOrder.objects.create(question=question, batch=self.batch, order=1)
        member_1 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_2 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_3 = HouseholdMember.objects.create(household=self.household_2, date_of_birth=datetime(2000, 02, 02))
        self.investigator_1.member_answered(question, member_1, 1, self.batch)
        self.investigator_1.member_answered(question, member_2, 1, self.batch)
        self.assertFalse(self.investigator_1.completed_survey(self.survey))
        self.investigator_1.member_answered(question, member_3, 1, self.batch)
        self.assertTrue(self.investigator_1.completed_survey(self.survey))

    def test_should_return_False_for_has_completed_survey_if_no_open_batch(self):
        self.batch.close_for_location(self.abim)
        member_group = HouseholdMemberGroup.objects.create(name='group1', order=1)
        question = Question.objects.create(text="some question", answer_type=Question.NUMBER, order=1,
                                           group=member_group)
        self.batch.questions.add(question)
        BatchQuestionOrder.objects.create(question=question, batch=self.batch, order=1)
        member_1 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_2 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_3 = HouseholdMember.objects.create(household=self.household_2, date_of_birth=datetime(2000, 02, 02))
        self.investigator_1.member_answered(question, member_1, 1, self.batch)
        self.investigator_1.member_answered(question, member_2, 1, self.batch)
        self.assertFalse(self.investigator_1.completed_survey(self.survey))
        self.investigator_1.member_answered(question, member_3, 1, self.batch)
        self.assertFalse(self.investigator_1.completed_survey(self.survey))

    def test_should_show_data_only_for_investigators_who_completed_the_survey(self):
        member_group = HouseholdMemberGroup.objects.create(name='group1', order=1)
        question = Question.objects.create(text="some question", answer_type=Question.NUMBER, order=1,
                                           group=member_group)
        self.batch.questions.add(question)
        BatchQuestionOrder.objects.create(question=question, batch=self.batch, order=1)
        member_1 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_2 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_3 = HouseholdMember.objects.create(household=self.household_2, date_of_birth=datetime(2000, 02, 02))
        self.investigator_1.member_answered(question, member_1, 1, self.batch)
        self.investigator_1.member_answered(question, member_2, 1, self.batch)

        data = [self.investigator_1.name, self.investigator_1.mobile_number]
        data.extend([loc.name for loc in self.investigator_1.location_hierarchy().values()])
        response = Investigator.generate_completion_report(self.survey)
        self.assertNotIn(data, response)

        self.investigator_1.member_answered(question, member_3, 1, self.batch)
        response = Investigator.generate_completion_report(self.survey)
        self.assertIn(data, response)

    def test_should_show_data_only_for_investigators_who_completed_a_selected_batch(self):
        batch = Batch.objects.create(name="Batch 2", survey=self.survey)
        member_group = HouseholdMemberGroup.objects.create(name='group1', order=1)
        question_1 = Question.objects.create(text="some question", answer_type=Question.NUMBER, order=1,
                                             group=member_group)
        question_2 = Question.objects.create(text="some question", answer_type=Question.NUMBER, order=1,
                                             group=member_group)
        self.batch.questions.add(question_1)
        batch.questions.add(question_2)
        batch.open_for_location(self.abim)

        BatchQuestionOrder.objects.create(question=question_1, batch=self.batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch, order=1)

        member_1 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))
        member_2 = HouseholdMember.objects.create(household=self.household_1, date_of_birth=datetime(2000, 02, 02))

        self.investigator_1.member_answered(question_1, member_1, 1, self.batch)

        data = [self.investigator_1.name, self.investigator_1.mobile_number]
        data.extend([loc.name for loc in self.investigator_1.location_hierarchy().values()])
        investigator_completion = Investigator.generate_completion_report(self.survey, self.batch)
        self.assertNotIn(data, investigator_completion)

        self.investigator_1.member_answered(question_1, member_2, 1, self.batch)
        investigator_completion = Investigator.generate_completion_report(self.survey, self.batch)
        self.assertIn(data, investigator_completion)