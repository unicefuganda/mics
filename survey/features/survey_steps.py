from random import randint

from lettuce import *
from survey.models.surveys import Survey
from survey.models.question import Question
from survey.features.page_objects.surveys import SurveyListPage, AddSurveyPage

@step(u'And I visit surveys listing page')
def and_i_visit_surveys_listing_page(step):
    world.page = SurveyListPage(world.browser)
    world.page.visit()

@step(u'And I have 100 surveys')
def and_i_have_100_surveys(step):
    for _ in xrange(100):
        random_number = randint(1, 99999)
        try:
            survey = Survey.objects.create(name='survey %d'%random_number, description= 'survey descrpition %d'%random_number, rapid_survey=(True if random_number%2 else False) )
        except Exception:
            pass

@step(u'Then I should see the survey list paginated')
def then_i_should_see_the_survey_list_paginated(step):
    world.page.validate_fields()
    world.page.validate_pagination()
    world.page.validate_fields()

@step(u'And if I click the add survey button')
def and_if_i_click_the_add_survey_button(step):
    world.page.click_link_by_text("Add Survey")

@step(u'Then I should see the new survey form')
def then_i_should_see_the_new_survey_form(step):
    world.page = AddSurveyPage(world.browser)
    world.page.validate_url()

@step(u'And I have a question')
def and_i_have_a_question(step):
    world.question = Question.objects.create(batch=world.batch, text="some questions",
                                                    answer_type=Question.NUMBER, order=1)

@step(u'And I visit the new survey page')
def and_i_visit_the_new_survey_page(step):
    world.page = AddSurveyPage(world.browser)
    world.page.visit()

@step(u'When I fill in the survey details')
def when_i_fill_in_the_survey_details(step):
    data = {'name': 'survey rajni',
            'description': 'survey description rajni',
            'number_of_household_per_investigator': 10,
            'rapid_survey': True,
            'questions': world.question.pk,
            }
    world.page.fill_valid_values(data)

@step(u'And I select the questions')
def and_i_select_the_questions(step):
    world.page.select_multiple('#id_questions', world.question)

@step(u'Then I should see that the survey was saved successfully')
def then_i_should_see_that_the_survey_was_saved_successfully(step):
    world.page.see_success_message('Survey', 'added')