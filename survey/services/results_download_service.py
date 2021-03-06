from rapidsms.contrib.locations.models import Location
from survey.models import LocationTypeDetails, Household, HouseholdMemberGroup
from survey.utils.views_helper import get_ancestors


class ResultsDownloadService(object):
    def __init__(self, survey=None, batch=None):
        self.batch = batch
        self.survey, self.questions = self._set_survey_and_questions(survey)

    def _set_survey_and_questions(self, survey):
        if self.batch:
            return self.batch.survey, self.batch.all_questions()
        return survey, survey.all_questions()

    def set_report_headers(self):
        header = list(LocationTypeDetails.get_ordered_types().exclude(name__iexact="country").values_list('name', flat=True))
        other_headers = ['Household ID', 'Name', 'Age', 'Month of Birth', 'Year of Birth', 'Gender']
        header.extend(other_headers)
        header.extend(self.question_headers())
        return header

    def question_headers(self):
        header = []
        for question in self.questions:
            header.append(question.identifier)
            if question.is_multichoice():
                header.append('')
        return header

    def get_summarised_answers(self):
        data = []
        all_households = Household.objects.filter(survey=self.survey)
        locations = list(set(all_households.values_list('ea__locations', flat=True)))
        general_group = HouseholdMemberGroup.objects.get(name="GENERAL")
        for location_id in locations:
            households_in_location = all_households.filter(ea__locations=location_id)
            household_location = households_in_location[0].location
            location_ancestors = self._get_ancestors_names(household_location, exclude_type='country')
            for household in households_in_location:
                for member in household.all_members():
                    member_gender = 'Male' if member.male else 'Female'
                    answers = location_ancestors
                    answers = answers + [household.household_code, member.surname, str(int(member.get_age())),
                                         str(member.get_month_of_birth()), str(member.get_year_of_birth()),
                                         member_gender]
                    answers = answers + member.answers_for(self.questions, general_group)
                    data.append(answers)
        return data

    def generate_report(self):
        data = [self.set_report_headers()]
        data.extend(self.get_summarised_answers())
        return data

    def _get_ancestors_names(self, household_location, exclude_type='country'):
        location_ancestors = get_ancestors(household_location, include_self=True)
        if exclude_type:
            exclude_location = Location.objects.filter(type__name__iexact=exclude_type.lower())
            for location in exclude_location:
                location_ancestors.remove(location)
        result= [ancestor.name for ancestor in location_ancestors]
        result.reverse()
        return result
