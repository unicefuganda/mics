from survey.models import Batch, Question, HouseholdMemberGroup, BatchQuestionOrder, QuestionModule
from survey.tests.base_test import BaseTest


class BatchQuestionOrderTest(BaseTest):
    def setUp(self):
        self.batch = Batch.objects.create(order=1)
        self.member_group = HouseholdMemberGroup.objects.create(name="Greater than 2 years", order=1)
        self.question_1 = Question.objects.create(text="Question 1?", answer_type=Question.NUMBER,
                                                  order=1, group=self.member_group)
        self.question_2 = Question.objects.create(text="Question 2?", answer_type=Question.NUMBER,
                                                  order=2, group=self.member_group)
        self.question_1.batches.add(self.batch)
        self.question_2.batches.add(self.batch)

    def test_fields(self):
        batch_question_order = BatchQuestionOrder()
        fields = [str(item.attname) for item in batch_question_order._meta.fields]
        self.assertEqual(6, len(fields))
        for field in ['id', 'created', 'modified', 'batch_id', 'question_id', 'order']:
            self.assertIn(field, fields)

    def test_store(self):
        batch_question_order = BatchQuestionOrder.objects.create(order=1, question=self.question_1, batch=self.batch)
        self.failUnless(batch_question_order.id)
        self.failUnless(batch_question_order.question_id)
        self.failUnless(batch_question_order.batch_id)

    def test_knows_the_order_for_question_is_one_for_first_question_assigned_in_batch(self):
        batch = Batch.objects.create(order=1, name="Batch A")
        self.assertEqual(1, BatchQuestionOrder.next_question_order_for(batch))

    def test_knows_order_is_plus_one_order_of_last_question_assigned_to_batch(self):
        question = Question.objects.create(text="This is a question", answer_type=Question.NUMBER)
        batch = Batch.objects.create(order=1, name="Batch A")
        question.batches.add(batch)

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        self.assertEqual(2, BatchQuestionOrder.next_question_order_for(batch))

    def test_order_is_not_dependent_on_another_batch(self):
        question = Question.objects.create(text="This is a question", answer_type=Question.NUMBER)
        question_2 = Question.objects.create(text="This is another question", answer_type=Question.NUMBER)
        question_3 = Question.objects.create(text="This is a question in other batch", answer_type=Question.NUMBER)
        batch = Batch.objects.create(order=1, name="Batch A")
        batch_2 = Batch.objects.create(order=2, name="Batch B")
        question.batches.add(batch)
        question_2.batches.add(batch_2)
        question_3.batches.add(batch_2)

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch_2, order=2)
        BatchQuestionOrder.objects.create(question=question_3, batch=batch_2, order=1)
        self.assertEqual(2, BatchQuestionOrder.next_question_order_for(batch))
        self.assertEqual(3, BatchQuestionOrder.next_question_order_for(batch_2))

    def test_knows_to_get_all_questions_for_batch_if_empty_filter_conditions(self):
        question = Question.objects.create(text="This is a question", answer_type=Question.NUMBER, order=1)
        question_2 = Question.objects.create(text="This is another question", answer_type=Question.NUMBER, order=2)
        question_3 = Question.objects.create(text="This is a question in other batch", answer_type=Question.NUMBER, order=3)
        batch = Batch.objects.create(order=1, name="Batch A")
        batch_2 = Batch.objects.create(order=2, name="Batch B")
        question.batches.add(batch)
        question_2.batches.add(batch_2)
        question_3.batches.add(batch_2)

        filter_condition = {}

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch_2, order=2)
        BatchQuestionOrder.objects.create(question=question_3, batch=batch_2, order=1)

        batch_1_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch.id, filter_condition)
        batch_2_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch_2.id, filter_condition)

        self.assertIn(question, batch_1_ordered_questions)
        self.assertIn(question_2, batch_2_ordered_questions)
        self.assertIn(question_3, batch_2_ordered_questions)
        self.assertEqual(question_2, batch_2_ordered_questions[1])
        self.assertEqual(question_3, batch_2_ordered_questions[0])

    def test_knows_to_get_all_questions_for_batch_for_a_particular_group_filter_conditions(self):
        another_member_group = HouseholdMemberGroup.objects.create(name="Greater than 6 years", order=2)

        question = Question.objects.create(text="This is a question", answer_type=Question.NUMBER, order=1, group=self.member_group)
        question_2 = Question.objects.create(text="This is another question", answer_type=Question.NUMBER, order=2, group=another_member_group)
        question_3 = Question.objects.create(text="This is a question in other batch", answer_type=Question.NUMBER, order=3, group=self.member_group)
        question_4 = Question.objects.create(text="This is another question again", answer_type=Question.NUMBER, order=4, group=another_member_group)

        batch = Batch.objects.create(order=1, name="Batch A")
        batch_2 = Batch.objects.create(order=2, name="Batch B")

        question.batches.add(batch)
        question_2.batches.add(batch)
        question_3.batches.add(batch_2)
        question_4.batches.add(batch_2)

        filter_condition = {}
        filter_condition['question__group__id'] = self.member_group.id

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch, order=2)
        BatchQuestionOrder.objects.create(question=question_3, batch=batch_2, order=1)
        BatchQuestionOrder.objects.create(question=question_4, batch=batch_2, order=2)

        batch_1_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch.id, filter_condition)
        batch_2_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch_2.id, filter_condition)

        self.assertIn(question, batch_1_ordered_questions)
        self.assertNotIn(question_2, batch_1_ordered_questions)
        self.assertIn(question_3, batch_2_ordered_questions)
        self.assertNotIn(question_4, batch_2_ordered_questions)

    def test_knows_to_get_all_questions_for_batch_for_a_particular_module_filter_conditions(self):
        module_1 = QuestionModule.objects.create(name="Module 1")
        module_2 = QuestionModule.objects.create(name="Module 2")

        question = Question.objects.create(text="This is a question", answer_type=Question.NUMBER, order=1, module=module_1)
        question_2 = Question.objects.create(text="This is another question", answer_type=Question.NUMBER, order=2, module=module_2)
        question_3 = Question.objects.create(text="This is a question in other batch", answer_type=Question.NUMBER, order=3, module=module_1)
        question_4 = Question.objects.create(text="This is another question again", answer_type=Question.NUMBER, order=4, module=module_2)

        batch = Batch.objects.create(order=1, name="Batch A")
        batch_2 = Batch.objects.create(order=2, name="Batch B")

        question.batches.add(batch)
        question_2.batches.add(batch)
        question_3.batches.add(batch_2)
        question_4.batches.add(batch_2)

        filter_condition = {}
        filter_condition['question__module__id'] = module_1.id

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch, order=2)
        BatchQuestionOrder.objects.create(question=question_3, batch=batch_2, order=1)
        BatchQuestionOrder.objects.create(question=question_4, batch=batch_2, order=2)

        batch_1_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch.id, filter_condition)
        batch_2_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch_2.id, filter_condition)

        self.assertIn(question, batch_1_ordered_questions)
        self.assertNotIn(question_2, batch_1_ordered_questions)
        self.assertIn(question_3, batch_2_ordered_questions)
        self.assertNotIn(question_4, batch_2_ordered_questions)

    def test_knows_to_get_all_questions_for_batch_for_a_particular_answer_type_filter_conditions(self):
        question = Question.objects.create(text="This is a question", answer_type=Question.NUMBER, order=1)
        question_2 = Question.objects.create(text="This is another question", answer_type=Question.TEXT, order=2)
        question_3 = Question.objects.create(text="This is a question in other batch", answer_type=Question.NUMBER, order=3)
        question_4 = Question.objects.create(text="This is another question again", answer_type=Question.TEXT, order=4)

        batch = Batch.objects.create(order=1, name="Batch A")
        batch_2 = Batch.objects.create(order=2, name="Batch B")

        question.batches.add(batch)
        question_2.batches.add(batch)
        question_3.batches.add(batch_2)
        question_4.batches.add(batch_2)

        filter_condition = {}
        filter_condition['question__answer_type'] = Question.NUMBER

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch, order=2)
        BatchQuestionOrder.objects.create(question=question_3, batch=batch_2, order=1)
        BatchQuestionOrder.objects.create(question=question_4, batch=batch_2, order=2)

        batch_1_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch.id, filter_condition)
        batch_2_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch_2.id, filter_condition)

        self.assertIn(question, batch_1_ordered_questions)
        self.assertNotIn(question_2, batch_1_ordered_questions)
        self.assertIn(question_3, batch_2_ordered_questions)
        self.assertNotIn(question_4, batch_2_ordered_questions)

    def test_knows_to_get_all_questions_for_batch_for_a_specific_set_of_conditions_for_filter(self):
        module_1 = QuestionModule.objects.create(name="Module 1")
        module_2 = QuestionModule.objects.create(name="Module 2")
        another_member_group = HouseholdMemberGroup.objects.create(name="Greater than 6 years", order=2)

        question = Question.objects.create(text="Question 1?", answer_type=Question.NUMBER, order=1,
                                           group=self.member_group, module=module_1)
        question_2 = Question.objects.create(text="Question 2?", answer_type=Question.TEXT, order=2,
                                             group=another_member_group, module=module_1)
        question_3 = Question.objects.create(text="Question 3?", answer_type=Question.NUMBER, order=2,
                                             group=self.member_group, module=module_2)
        question_4 = Question.objects.create(text="Question 4?", answer_type=Question.TEXT, order=2,
                                             group=another_member_group, module=module_2)

        question_5 = Question.objects.create(text="Question 5?", answer_type=Question.NUMBER, order=3,
                                             group=self.member_group, module=module_1)
        question_6 = Question.objects.create(text="Question 6?", answer_type=Question.TEXT, order=4,
                                             group=another_member_group, module=module_1)
        question_7 = Question.objects.create(text="Question 6?", answer_type=Question.NUMBER, order=4,
                                             group=self.member_group, module=module_2)
        question_8 = Question.objects.create(text="Question 6?", answer_type=Question.TEXT, order=4,
                                             group=another_member_group, module=module_2)

        batch = Batch.objects.create(order=1, name="Batch A")
        batch_2 = Batch.objects.create(order=2, name="Batch B")

        question.batches.add(batch)
        question_2.batches.add(batch)
        question_3.batches.add(batch)
        question_4.batches.add(batch)

        question_5.batches.add(batch_2)
        question_6.batches.add(batch_2)
        question_7.batches.add(batch_2)
        question_8.batches.add(batch_2)

        filter_condition = {}
        filter_condition['question__group__id'] = self.member_group.id
        filter_condition['question__module__id'] = module_1.id
        filter_condition['question__answer_type'] = Question.NUMBER

        BatchQuestionOrder.objects.create(question=question, batch=batch, order=1)
        BatchQuestionOrder.objects.create(question=question_2, batch=batch, order=2)
        BatchQuestionOrder.objects.create(question=question_3, batch=batch, order=3)
        BatchQuestionOrder.objects.create(question=question_4, batch=batch, order=4)

        BatchQuestionOrder.objects.create(question=question_5, batch=batch_2, order=1)
        BatchQuestionOrder.objects.create(question=question_6, batch=batch_2, order=2)
        BatchQuestionOrder.objects.create(question=question_7, batch=batch_2, order=3)
        BatchQuestionOrder.objects.create(question=question_8, batch=batch_2, order=4)

        batch_1_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch.id, filter_condition)
        batch_2_ordered_questions = BatchQuestionOrder.get_batch_order_specific_questions(batch_2.id, filter_condition)

        self.assertIn(question, batch_1_ordered_questions)
        self.assertNotIn(question_2, batch_1_ordered_questions)
        self.assertNotIn(question_3, batch_1_ordered_questions)
        self.assertNotIn(question_4, batch_1_ordered_questions)
        self.assertIn(question_5, batch_2_ordered_questions)
        self.assertNotIn(question_6, batch_2_ordered_questions)
        self.assertNotIn(question_7, batch_2_ordered_questions)
        self.assertNotIn(question_8, batch_2_ordered_questions)

