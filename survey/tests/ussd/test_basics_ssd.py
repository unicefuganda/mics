# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import datetime
from random import randint
import urllib2
from django.test import TestCase, Client
from rapidsms.contrib.locations.models import Location
from survey.investigator_configs import COUNTRY_PHONE_CODE
from survey.models import Investigator, Backend, Household, HouseholdHead, Batch, HouseholdMemberGroup, NumericalAnswer, Question, TextAnswer, QuestionOption, MultiChoiceAnswer, AnswerRule
from survey.models.households import HouseholdMember
from survey.ussd import USSD


class USSDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.ussd_params = {
            'transactionId': "123344" + str(randint(1, 99999)),
            'transactionTime': datetime.datetime.now().strftime('%Y%m%dT%H:%M:%S'),
            'msisdn': '2567765' + str(randint(1, 99999)),
            'ussdServiceCode': '130',
            'ussdRequestString': '',
            'response': "false"
        }
        self.investigator = Investigator.objects.create(name="investigator name",
                                                        mobile_number=self.ussd_params['msisdn'].replace(
                                                            COUNTRY_PHONE_CODE, ''),
                                                        location=Location.objects.create(name="Kampala"),
                                                        backend=Backend.objects.create(name='something'))
        self.household = Household.objects.create(investigator=self.investigator, uid=0)
        self.household_head = HouseholdHead.objects.create(household=self.household, surname="Surname",
                                                           date_of_birth='1980-09-01')
        self.household_1 = Household.objects.create(investigator=self.investigator, uid=1)
        self.household_head_1 = HouseholdHead.objects.create(
            household=self.household_1,
            surname="Name " + str(randint(1, 9999)), date_of_birth='1980-09-01')
        self.household_member = HouseholdMember.objects.create(surname="Name 2", household=self.household_1,
                                                               date_of_birth='2000-02-03')
        self.batch = Batch.objects.create(order=1)
        self.batch.open_for_location(self.investigator.location)
        self.member_group = HouseholdMemberGroup.objects.create(name="5 to 6 years", order=0)

    def reset_session(self):
        self.ussd_params['transactionId'] = "123344" + str(randint(1, 99999))
        self.ussd_params['response'] = 'false'
        self.ussd_params['ussdRequestString'] = ''

    def select_household(self, household_id="1"):
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"
        self.client.post('/ussd', data=self.ussd_params)

        self.ussd_params['ussdRequestString'] = household_id
        return self.client.post('/ussd', data=self.ussd_params)

    def set_questions_answered_to_twenty_minutes_ago(self):
        for answer in NumericalAnswer.objects.all():
            answer.created -= datetime.timedelta(minutes=(20), seconds=1)
            answer.save()

    def test_list_household_members_after_selecting_household(self):
        household_member1 = HouseholdMember.objects.create(household=self.household, surname="abcd", male=False,
                                                           date_of_birth='1989-02-02')
        household_member2 = HouseholdMember.objects.create(household=self.household, surname="xyz", male=False,
                                                           date_of_birth='1989-02-02')
        response = self.select_household()
        members_list = "%s\n1: %s - (HEAD)*\n2: %s*\n3: %s*" % (
            USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname, household_member1.surname,
            household_member2.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_no_households(self):
        investigator = Investigator.objects.create(name="investigator name", mobile_number="1234567890",
                                                   location=self.investigator.location,
                                                   backend=Backend.objects.create(name='something1'))
        self.ussd_params['msisdn'] = investigator.mobile_number
        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=end" % USSD.MESSAGES['NO_HOUSEHOLDS']
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_numerical_questions(self):
        HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="How many of them are male?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        self.select_household()
        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % question_1.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "4"

        response = self.client.post('/ussd', data=self.ussd_params)

        self.assertEquals(4, NumericalAnswer.objects.get(investigator=self.investigator, question=question_1).answer)

        response_string = "responseString=%s&action=request" % question_2.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(2, NumericalAnswer.objects.get(investigator=self.investigator, question=question_2).answer)

    def test_textual_questions(self):
        member_2 = HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.TEXT, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="How many of them are male?",
                                             answer_type=Question.TEXT, order=2, group=self.member_group)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        self.select_household()
        response = self.select_household_member()

        response_string = "responseString=%s&action=request" % question_1.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "Reply one"

        response = self.client.post('/ussd', data=self.ussd_params)

        self.assertEquals(self.ussd_params['ussdRequestString'],
                          TextAnswer.objects.get(investigator=self.investigator, question=question_1).answer)

        response_string = "responseString=%s&action=request" % question_2.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['ussdRequestString'] = "Reply Two"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(self.ussd_params['ussdRequestString'],
                          TextAnswer.objects.get(investigator=self.investigator, question=question_2).answer)

    def test_multichoice_questions(self):
        HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.MULTICHOICE, order=1, group=self.member_group)
        option_1_1 = QuestionOption.objects.create(question=question_1, text="OPTION 1", order=1)
        option_1_2 = QuestionOption.objects.create(question=question_1, text="OPTION 2", order=2)

        question_2 = Question.objects.create(text="How many of them are male?",
                                             answer_type=Question.MULTICHOICE, order=2, group=self.member_group)
        option_2_1 = QuestionOption.objects.create(question=question_2, text="OPTION 1", order=1)
        option_2_2 = QuestionOption.objects.create(question=question_2, text="OPTION 2", order=2)

        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        self.select_household()
        response = self.select_household_member()

        response_string = "responseString=%s&action=request" % question_1.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = str(option_1_1.order)

        response = self.client.post('/ussd', data=self.ussd_params)

        self.assertEquals(option_1_1,
                          MultiChoiceAnswer.objects.get(investigator=self.investigator, question=question_1).answer)

        response_string = "responseString=%s&action=request" % question_2.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['ussdRequestString'] = str(option_2_1.order)

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(option_2_1,
                          MultiChoiceAnswer.objects.get(investigator=self.investigator, question=question_2).answer)

    def test_multichoice_questions_pagination(self):
        question = Question.objects.create(text="This is a question",
                                           answer_type=Question.MULTICHOICE, order=1, group=self.member_group)
        option_1 = QuestionOption.objects.create(question=question, text="OPTION 1", order=1)
        option_2 = QuestionOption.objects.create(question=question, text="OPTION 2", order=2)
        option_3 = QuestionOption.objects.create(question=question, text="OPTION 3", order=3)
        option_4 = QuestionOption.objects.create(question=question, text="OPTION 4", order=4)
        option_5 = QuestionOption.objects.create(question=question, text="OPTION 5", order=5)
        option_6 = QuestionOption.objects.create(question=question, text="OPTION 6", order=6)
        option_7 = QuestionOption.objects.create(question=question, text="OPTION 7", order=7)
        back_text = Question.PREVIOUS_PAGE_TEXT
        next_text = Question.NEXT_PAGE_TEXT

        question_2 = Question.objects.create(text="This is a question",
                                             answer_type=Question.MULTICHOICE, order=2, group=self.member_group)
        option_8 = QuestionOption.objects.create(question=question_2, text="OPTION 1", order=1)
        option_9 = QuestionOption.objects.create(question=question_2, text="OPTION 2", order=2)

        question.batches.add(self.batch)
        question_2.batches.add(self.batch)

        page_1 = "%s\n1: %s\n2: %s\n3: %s\n%s" % (question.text, option_1.text, option_2.text, option_3.text, next_text)
        page_2 = "%s\n4: %s\n5: %s\n6: %s\n%s\n%s" % (
            question.text, option_4.text, option_5.text, option_6.text, back_text, next_text)
        page_3 = "%s\n7: %s\n%s" % (question.text, option_7.text, back_text)

        self.select_household()
        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % page_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "#"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % page_2
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "#"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % page_3
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "*"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % page_2
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "*"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % page_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "#"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % page_2
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_2.to_ussd()
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_reanswer_question(self):
        HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="How many of them are male?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)
        rule = AnswerRule.objects.create(question=question_2, action=AnswerRule.ACTIONS['REANSWER'],
                                         condition=AnswerRule.CONDITIONS['GREATER_THAN_QUESTION'],
                                         validate_with_question=question_1)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        self.select_household()
        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "5"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "10"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("RECONFIRM: " + question_1.text)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "5"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("RECONFIRM: " + question_2.text)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_text_invalid_answer(self):
        member_2 = HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.TEXT, order=1, group=self.member_group)

        question_1.batches.add(self.batch)

        self.select_household()

        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = ""

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("INVALID ANSWER: " + question_1.text)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "something"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_numerical_invalid_answer(self):
        HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_1.batches.add(self.batch)

        self.select_household()
        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "a"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("INVALID ANSWER: " + question_1.text)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_multichoice_invalid_answer(self):
        HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="This is a question",
                                             answer_type=Question.MULTICHOICE, order=1, group=self.member_group)
        question_1.batches.add(self.batch)
        option_1 = QuestionOption.objects.create(question=question_1, text="OPTION 1", order=1)
        option_2 = QuestionOption.objects.create(question=question_1, text="OPTION 2", order=2)
        self.select_household()
        response = self.select_household_member()
        page_1 = "%s\n1: %s\n2: %s" % (question_1.text, option_1.text, option_2.text)

        response_string = "responseString=%s&action=request" % page_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "a"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("INVALID ANSWER: " + page_1)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "4"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("INVALID ANSWER: " + page_1)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_end_interview_confirmation(self):
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2= Question.objects.create(text="How many of them are male?",
                                answer_type=Question.NUMBER, order=2, group=self.member_group)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)
        AnswerRule.objects.create(question=question_1, action=AnswerRule.ACTIONS['END_INTERVIEW'],
                                  condition=AnswerRule.CONDITIONS['EQUALS'], validate_with_value=0)

        response = self.select_household()

        members_list = "%s\n1: %s - (HEAD)" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.investigator = Investigator.objects.get(id=self.investigator.pk)

        self.assertEquals(len(self.investigator.get_from_cache('CONFIRM_END_INTERVIEW')), 0)

        response = self.select_household_member("1")
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.investigator = Investigator.objects.get(id=self.investigator.pk)

        self.assertEquals(len(self.investigator.get_from_cache('CONFIRM_END_INTERVIEW')), 0)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "0"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("RECONFIRM: " + question_1.text)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(len(self.investigator.get_from_cache('CONFIRM_END_INTERVIEW')), 1)

        self.assertEquals(0, NumericalAnswer.objects.count())

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "0"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['HOUSEHOLD_COMPLETION_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.investigator = Investigator.objects.get(id=self.investigator.pk)
        self.assertEquals(len(self.investigator.get_from_cache('CONFIRM_END_INTERVIEW')), 0)
        self.assertFalse(self.household.has_pending_survey())
        self.assertTrue(self.household_1.has_pending_survey())
        self.assertFalse(self.investigator.completed_open_surveys())

        self.set_questions_answered_to_twenty_minutes_ago()

        self.ussd_params['response'] = "false"
        self.ussd_params['ussdRequestString'] = ""
        self.ussd_params['transactionId'] = "123344" + str(randint(1, 99999))

        homepage = "Welcome %s to the survey.\n00: Households list" % self.investigator.name
        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % homepage
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"

        households_list_1 = "%s\n1: %s*\n2: %s" % (
            USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head.surname, self.household_head_1.surname)

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        response = self.select_household_member(member_id="2")
        members_list = "%s\n1: %s - (HEAD)\n2: %s" % (
            USSD.MESSAGES['MEMBERS_LIST'], self.household_head_1.surname, self.household_member.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "false"
        self.ussd_params['ussdRequestString'] = ""
        self.ussd_params['transactionId'] = "123344" + str(randint(1, 99999))

        homepage = "Welcome %s to the survey.\n00: Households list" % self.investigator.name
        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % homepage
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"

        households_list_1 = "%s\n1: %s*\n2: %s" % (
            USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head.surname, self.household_head_1.surname)

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        response = self.select_household('1')
        members_list = "%s\n1: %s - (HEAD)*" % (
            USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def select_household_member(self, member_id="1"):
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = member_id
        return self.client.post('/ussd', data=self.ussd_params)

    def test_end_interview_confirmation_alternative(self):
        question_1 = Question.objects.create(text="How many members are there in this household?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="How many of them are male?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)
        rule = AnswerRule.objects.create(question=question_1, action=AnswerRule.ACTIONS['END_INTERVIEW'],
                                         condition=AnswerRule.CONDITIONS['EQUALS'], validate_with_value=0)

        response = self.select_household()
        members_list = "%s\n1: %s - (HEAD)" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.investigator = Investigator.objects.get(id=self.investigator.pk)

        self.assertEquals(len(self.investigator.get_from_cache('CONFIRM_END_INTERVIEW')), 0)

        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "0"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("RECONFIRM: " + question_1.text)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(0, NumericalAnswer.objects.count())

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_should_show_member_completion_message_and_choose_to_go_to_member_list(self):
        member_2 = HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="Question 1?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="Question 2?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)

        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        response = self.select_household()

        members_list = "%s\n1: %s - (HEAD)\n2: %s" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname, member_2.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        response = self.select_household_member("1")
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        members_list = "%s\n1: %s - (HEAD)*\n2: %s" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname, member_2.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_should_show_member_completion_message_and_choose_to_go_to_household_list(self):
        member_2 = HouseholdMember.objects.create(surname="Name 2", household=self.household, date_of_birth='1980-02-03')
        question_1 = Question.objects.create(text="Question 1?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="Question 2?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        response = self.select_household()

        members_list = "%s\n1: %s - (HEAD)\n2: %s" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname, member_2.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        response = self.select_household_member("1")
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        households_list_1 = "%s\n1: %s\n2: %s" % (USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head.surname, self.household_head_1.surname)

        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_should_show_thank_you_message_on_completion_of_all_members_questions(self):
        question_1 = Question.objects.create(text="Question 1?",
                                             answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="Question 2?",
                                             answer_type=Question.NUMBER, order=2, group=self.member_group)
        question_1.batches.add(self.batch)
        question_2.batches.add(self.batch)

        response = self.select_household()

        members_list = "%s\n1: %s - (HEAD)" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head.surname)
        response_string = "responseString=%s&action=request" % members_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        response = self.select_household_member("1")
        response_string = "responseString=%s&action=request" % question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['HOUSEHOLD_COMPLETION_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        households_list_1 = "%s\n1: %s*\n2: %s" % (USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head.surname, self.household_head_1.surname)

        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)