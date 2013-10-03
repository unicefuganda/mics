# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import datetime
from random import randint
import urllib2
from django.test import TestCase, Client
from rapidsms.contrib.locations.models import Location
from survey.investigator_configs import COUNTRY_PHONE_CODE
from survey.models import Household, HouseholdHead, Investigator, Backend, HouseholdMemberGroup, GroupCondition, Batch, Question, NumericalAnswer, HouseholdBatchCompletion
from survey.models.households import HouseholdMember
from survey.ussd import USSD


class USSDTestCompleteFlow(TestCase):
    def create_household_head(self, uid):
        self.household = Household.objects.create(investigator=self.investigator, uid=uid)
        return HouseholdHead.objects.create(household=self.household,
                                            surname="Name " + str(randint(1, 9999)), date_of_birth=datetime.date(1980, 9, 1))

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

        self.head_group = HouseholdMemberGroup.objects.create(name="General", order=0)
        self.condition = GroupCondition.objects.create(value='HEAD', attribute="GENERAL", condition="EQUALS")
        self.condition.groups.add(self.head_group)

        self.member_group = HouseholdMemberGroup.objects.create(name="Less than 10", order=1)
        self.member_condition = GroupCondition.objects.create(value=10, attribute="AGE", condition="LESS_THAN")
        self.member_condition.groups.add(self.member_group)

        self.household_head_1 = self.create_household_head(0)
        self.household_head_2 = self.create_household_head(1)
        self.household_head_3 = self.create_household_head(2)
        self.household_head_4 = self.create_household_head(3)
        self.household_head_5 = self.create_household_head(4)
        self.household_head_6 = self.create_household_head(5)
        self.household_head_7 = self.create_household_head(6)
        self.household_head_8 = self.create_household_head(7)
        self.household_head_9 = self.create_household_head(8)

        self.batch = Batch.objects.create(name="Batch A", order=1)
        self.batch_b = Batch.objects.create(name="Batch B", order=2)
        self.batch.open_for_location(self.investigator.location)
        self.question_1 = Question.objects.create(text="How many members are there in this household?",
                                                  answer_type=Question.NUMBER, order=1, group=self.head_group)

        self.question_2 = Question.objects.create(text="How many of them are male?",
                                                  answer_type=Question.NUMBER, order=2, group=self.head_group)
        self.question_1_b = Question.objects.create(text="How many members are there in this household? Batch B",
                                                answer_type=Question.NUMBER, order=3, group=self.head_group)
        self.question_3 = Question.objects.create(text="Question for member group?",
                                                  answer_type=Question.NUMBER, order=1, group=self.member_group)

        self.question_1.batches.add(self.batch)
        self.question_2.batches.add(self.batch)
        self.question_3.batches.add(self.batch)

        self.question_1_b.batches.add(self.batch_b)

    def select_household(self, household=1):
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"
        response = self.client.post('/ussd', data=self.ussd_params)
        self.ussd_params['ussdRequestString'] = str(household)
        return self.client.post('/ussd', data=self.ussd_params)

    def select_household_member(self, member_id="1"):
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = member_id
        return self.client.post('/ussd', data=self.ussd_params)

    def create_household_member(self, member_name, household):
        return HouseholdMember.objects.create(surname="member %s" % member_name, date_of_birth=datetime.date(2012, 2, 2), male=True,
                                              household=household)

    def test_household_member_list_paginates(self):
        household = Household.objects.get(uid=0)
        member_1 = self.create_household_member("1", household)
        member_2 = self.create_household_member("2", household)
        member_3 = self.create_household_member("3", household)
        member_4 = self.create_household_member("4", household)
        member_5 = self.create_household_member("5", household)
        member_6 = self.create_household_member("6", household)
        member_7 = self.create_household_member("7", household)

        member_list_1 = "%s\n1: %s - (HEAD)\n2: %s\n3: %s\n4: %s\n#: Next" % (
            USSD.MESSAGES['MEMBERS_LIST'], self.household_head_1.surname, member_1.surname,
            member_2.surname, member_3.surname)

        member_list_2 = "%s\n5: %s\n6: %s\n7: %s\n8: %s\n*: Back" % (
            USSD.MESSAGES['MEMBERS_LIST'], member_4.surname, member_5.surname,
            member_6.surname, member_7.surname)

        response = self.select_household()
        response_string = "responseString=%s&action=request" % member_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "#"
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % member_list_2
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "*"
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % member_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "100"
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % ("INVALID SELECTION: " + member_list_1)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "asda"
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % ("INVALID SELECTION: " + member_list_1)
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def set_questions_answered_to_twenty_minutes_ago(self):
        for answer in NumericalAnswer.objects.all():
            answer.created -= datetime.timedelta(minutes=(20), seconds=1)
            answer.save()

    def test_flow(self):
        self.batch.open_for_location(self.investigator.location)
        self.batch_b.close_for_location(self.investigator.location)
        household1_member = self.create_household_member("Member 1", self.household_head_1.household)
        household2_member = self.create_household_member("Member 2", self.household_head_2.household)

        homepage = "Welcome %s to the survey.\n00: Households list" % self.investigator.name

        self.ussd_params['ussdRequestString'] = "adassd"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % homepage
        self.assertEquals(urllib2.unquote(response.content), response_string)

        households_list_1 = "%s\n1: %s\n2: %s\n3: %s\n4: %s\n#: Next" % (
            USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head_1.surname, self.household_head_2.surname,
            self.household_head_3.surname, self.household_head_4.surname)

        households_list_2 = "%s\n5: %s\n6: %s\n7: %s\n8: %s\n*: Back\n#: Next" % (
            USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head_5.surname, self.household_head_6.surname,
            self.household_head_7.surname, self.household_head_8.surname)

        households_list_3 = "%s\n9: %s\n*: Back" % (USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head_9.surname)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "#"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_2
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "#"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_3
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "*"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_2
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "*"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "100"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("INVALID SELECTION: " + households_list_1)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "adss"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % ("INVALID SELECTION: " + households_list_1)
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        self.client.post('/ussd', data=self.ussd_params)

        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % self.question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "10"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % self.question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(10, NumericalAnswer.objects.get(investigator=self.investigator, question=self.question_1,
                                                          householdmember=self.household_head_1).answer)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "5"
        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(5, NumericalAnswer.objects.get(investigator=self.investigator, question=self.question_2,
                                                         household=self.household_head_1.household).answer)

        # Deleting all the households except 1 and 2

        self.household_head_3.household.delete()
        self.household_head_4.household.delete()
        self.household_head_5.household.delete()
        self.household_head_6.household.delete()
        self.household_head_7.household.delete()
        self.household_head_8.household.delete()
        self.household_head_9.household.delete()

        # Survey for the next household

        self.set_questions_answered_to_twenty_minutes_ago()

        self.ussd_params['response'] = "false"
        self.ussd_params['ussdRequestString'] = ""
        self.ussd_params['transactionId'] = "123344" + str(randint(1, 99999))

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % homepage
        self.assertEquals(urllib2.unquote(response.content), response_string)

        households_list_1 = "%s\n1: %s\n2: %s" % (
            USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head_1.surname, self.household_head_2.surname)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        self.client.post('/ussd', data=self.ussd_params)
        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % self.question_1.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "10"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % self.question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(10, NumericalAnswer.objects.get(investigator=self.investigator, question=self.question_1,
                                                          household=self.household_head_2.household).answer)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "5"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['MEMBER_SUCCESS_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % self.question_3.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "20"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % USSD.MESSAGES['HOUSEHOLD_COMPLETION_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "2"

        response = self.client.post('/ussd', data=self.ussd_params)
        households_list = "%s\n1: %s\n2: %s*" % (USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head_1.surname, self.household_head_2.surname)
        response_string = "responseString=%s&action=request" % households_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        response = self.client.post('/ussd', data=self.ussd_params)

        households_member_list = "%s\n1: %s - (HEAD)*\n2: %s" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head_1.surname, household1_member.surname)
        response_string = "responseString=%s&action=request" % households_member_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

        response = self.select_household_member("2")

        response_string = "responseString=%s&action=request" % self.question_3.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "30"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=end" % USSD.MESSAGES['SUCCESS_MESSAGE_FOR_COMPLETING_ALL_HOUSEHOLDS']

        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.assertEquals(5, NumericalAnswer.objects.get(investigator=self.investigator, question=self.question_2,
                                                         household=self.household_head_2.household).answer)
        self.assertEquals(20, NumericalAnswer.objects.get(investigator=self.investigator, question=self.question_3,
                                                         household=self.household_head_2.household).answer)
        self.assertEquals(30, NumericalAnswer.objects.get(investigator=self.investigator, question=self.question_3,
                                                         household=self.household_head_1.household).answer)

    def test_should_ask_to_resume_questions_or_go_back_to_member_list_upon_session_timeout_or_session_cancel(self):
        homepage = "Welcome %s to the survey.\n00: Households list" % self.investigator.name

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % homepage
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.select_household()
        self.select_household_member()

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"
        response = self.client.post('/ussd', data=self.ussd_params)

        self.ussd_params['transactionId']=randint(89999, 9000000)
        self.ussd_params['response']= "false"
        self.ussd_params['ussdRequestString']= ""
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % USSD.MESSAGES['RESUME_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = USSD.ANSWER["YES"]
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % self.question_2.text
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['transactionId']=randint(89999, 9000000)
        self.ussd_params['response']= "false"
        self.ussd_params['ussdRequestString']= ""
        response = self.client.post('/ussd', data=self.ussd_params)

        response_string = "responseString=%s&action=request" % USSD.MESSAGES['RESUME_MESSAGE']
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = USSD.ANSWER["NO"]
        response = self.client.post('/ussd', data=self.ussd_params)

        households_member_list = "%s\n1: %s - (HEAD)" % (USSD.MESSAGES['MEMBERS_LIST'], self.household_head_1.surname)
        response_string = "responseString=%s&action=request" % households_member_list
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_show_completion_star_next_to_household_head_name(self):
        self.household_head_1.batch_completed(self.batch)
        self.household_head_3.batch_completed(self.batch)
        homepage = "Welcome %s to the survey.\n00: Households list" % self.investigator.name

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % homepage
        self.assertEquals(urllib2.unquote(response.content), response_string)

        households_list_1 = "%s\n1: %s*\n2: %s\n3: %s*\n4: %s\n#: Next" % (
            USSD.MESSAGES['HOUSEHOLD_LIST'], self.household_head_1.surname, self.household_head_2.surname,
            self.household_head_3.surname, self.household_head_4.surname)
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

    def test_completed_batch_timeout_for_household_after_5_min_should_allow_other_batches(self):
        self.household_head_1.household.batch_completed(self.batch)
        self.investigator.member_answered(self.question_1, self.household_head_1, 1, self.batch)
        self.investigator.member_answered(self.question_2, self.household_head_1, 1, self.batch)

        completion = HouseholdBatchCompletion.objects.filter(batch=self.batch)[0]

        latest_answer = NumericalAnswer.objects.all().latest()
        latest_answer.created -= datetime.timedelta(minutes=(USSD.TIMEOUT_MINUTES + 1), seconds=1)
        latest_answer.save()

        answer_one = NumericalAnswer.objects.filter(question=self.question_1)[0]
        answer_one.created -= datetime.timedelta(minutes=(USSD.TIMEOUT_MINUTES + 2), seconds=1)
        answer_one.save()

        self.batch.close_for_location(self.investigator.location)
        self.batch_b.open_for_location(self.investigator.location)
        self.client.post('/ussd', data=self.ussd_params)

        households_list_1 = "%s\n1: %s\n2: %s\n3: %s\n4: %s\n#: Next" % (USSD.MESSAGES['HOUSEHOLD_LIST'],
                                                                         self.household_head_1.surname,
                                                                         self.household_head_2.surname,
                                                                         self.household_head_3.surname,
                                                                         self.household_head_4.surname)
        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "00"

        response = self.client.post('/ussd', data=self.ussd_params)
        response_string = "responseString=%s&action=request" % households_list_1
        self.assertEquals(urllib2.unquote(response.content), response_string)

        self.ussd_params['response'] = "true"
        self.ussd_params['ussdRequestString'] = "1"

        self.client.post('/ussd', data=self.ussd_params)
        response = self.select_household_member()
        response_string = "responseString=%s&action=request" % self.question_1_b.text
        self.assertEquals(urllib2.unquote(response.content), response_string)