"""Offline regression cases for mixed exam forms and model output boundaries."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from exam_schema import parse_groups, validate_answers, SchemaError
from exam_runner import ExamSolver


MIXED = '''<div id="main-content"><div class="itest-section"><p>Read: The train leaves at noon.</p>
<div class="itest-ques-set"><p>Choose and explain.</p>
<label><input qid="1" name="r" type="radio" value="x">Noon</label>
<label><input qid="1" name="r" type="radio" value="y">Midnight</label>
<label><input qid="2" name="c" type="checkbox" value="a">One</label>
<label><input qid="2" name="c" type="checkbox" value="b">Two</label>
<input qid="3" name="t" maxlength="12">
<textarea qid="4" name="w"></textarea>
<select qid="5" name="s"><option value="">Choose</option><option value="v">Verb</option></select>
</div></div></div>'''
ANSWERS = [{'id': 'r', 'value': 'x'}, {'id': 'c', 'value': ['b', 'a']},
           {'id': 't', 'value': 'noon'}, {'id': 'w', 'value': 'The train leaves at noon.'}, {'id': 's', 'value': 'v'}]


class ExamSchemaTests(unittest.TestCase):
    def test_mixed_context_and_types(self):
        group = parse_groups(MIXED)[0]
        self.assertIn('The train leaves at noon.', group['context'])
        self.assertEqual(group['audio'], [])
        self.assertEqual([q['type'] for q in group['questions']], ['radio', 'checkbox', 'text', 'textarea', 'select'])
        self.assertEqual(validate_answers(group, ANSWERS)[1]['value'], ['a', 'b'])

    def test_unrecognized_group_is_not_silently_skipped(self):
        html = MIXED.replace('</div></div></div>', '</div><div class="itest-ques-set">Record your speech.</div></div></div>')
        with self.assertRaises(SchemaError):
            parse_groups(html)

    def test_invalid_model_output_stops(self):
        group = parse_groups(MIXED)[0]
        for answers in (ANSWERS[:-1], ANSWERS + ANSWERS[:1], [{'id': 'css', 'value': 'x'}],
                        [{**a, 'value': 1} for a in ANSWERS],
                        [a if a['id'] != 'c' else {**a, 'value': ['a', 'a']} for a in ANSWERS],
                        [a if a['id'] != 't' else {**a, 'value': 'x' * 13} for a in ANSWERS]):
            with self.subTest(answers=answers), self.assertRaises(SchemaError):
                validate_answers(group, answers)

    def test_unknown_and_incomplete_schema_stops(self):
        for html in (MIXED.replace('maxlength="12"', 'type="file"'),
                     MIXED.replace('name="w"', 'name="t"'),
                     MIXED.replace('</div></div></div>', '<img src="diagram.png"></div></div></div>'),
                     MIXED.replace('</div></div></div>', '</div><input qid="6" name="missing"></div></div>')):
            with self.subTest(html=html), self.assertRaises(SchemaError):
                parse_groups(html)

    def test_legacy_radio_answers(self):
        group = {'questions': [{'id': 'q', 'options': [{'value': '1'}]}]}
        self.assertEqual(validate_answers(group, [{'id': 'q', 'value': '1'}]), [{'id': 'q', 'value': '1'}])

    def test_text_only_never_downloads_or_transcribes(self):
        with tempfile.TemporaryDirectory() as folder:
            solver = ExamSolver({}, Path(folder))
            with patch.object(solver, 'download') as download, patch.object(solver, 'transcribe') as transcribe, patch.object(solver, 'solve_group', return_value=validate_answers(parse_groups(MIXED)[0], ANSWERS)):
                self.assertEqual(len(solver.prepare(parse_groups(MIXED))), 5)
                download.assert_not_called()
                transcribe.assert_not_called()

    def test_no_audio_context_does_not_drop_questions(self):
        group = parse_groups(MIXED.replace('<p>Choose and explain.</p>', '<span class="itest-hear-reslist">["https://itestres.unipus.cn/quesres/test.mp3"]</span>'))[0]
        self.assertEqual(len(group['questions']), 5)
        self.assertEqual(len(group['audio']), 1)

    def test_mixed_paper_loads_legacy_recordings_and_ignores_playlist_pauses(self):
        root = 'https://itestres.unipus.cn/itest-product/'
        old_paths = ['resourcefile/201311/passage.mp3', 'mr/quesx4/question.mp3']
        urls = [root + path for path in old_paths]
        playlist = json.dumps([urls[0], '2', urls[1], 15, urls[0]])
        hearing = f'<div class="itest-ques-set"><div class="itest-hear-reslist">{playlist}</div><input qid="6" name="listening"></div>'
        html = MIXED.replace('</div></div></div>', '</div>' + hearing + '</div></div>')
        written, listening = parse_groups(html)
        self.assertEqual(written['audio'], [])
        self.assertIn('textarea', [q['type'] for q in written['questions']])
        self.assertEqual(listening['audio'], urls)

    def test_missing_or_untrusted_recordings_do_not_become_text_only(self):
        valid = 'https://itestres.unipus.cn/quesres/test.mp3'
        for entries in (['15'], [valid, 'https://example.com/quesres/audio.mp3']):
            html = MIXED.replace('<p>Choose and explain.</p>', f'<span class="itest-hear-reslist">{json.dumps(entries)}</span>')
            with self.subTest(entries=entries), self.assertRaises(SchemaError):
                parse_groups(html)


if __name__ == '__main__':
    unittest.main()
