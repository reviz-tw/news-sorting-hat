import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


class PresentationModuleTests(unittest.TestCase):
    def setUp(self):
        self.catalog = read('schemas/presentation-modules.json')
        self.templates = read('schemas/article-templates.json')
        self.files = read(Path('schemas') / self.catalog['component_catalog'])['files']
        self.modules = {name: read(Path('schemas') / path) for name, path in self.files.items()}

    def test_supported_modules_match_output_contract(self):
        variants = read('schemas/presentation.schema.json')['properties']['blocks']['items']['oneOf']
        refs = [v['$ref'] for v in variants]
        expected = [self.files[name] + '#/$defs/frontend_schema' for name, m in self.modules.items()
                    if m['availability'] == 'supported']
        self.assertCountEqual(refs, expected)
        self.assertEqual(len(set(self.files.values())), len(self.files))
        for name, module in self.modules.items():
            self.assertEqual(name, module['id'])
            self.assertIn(module['availability'], ('supported', 'planning_only'))
            self.assertTrue((ROOT / module['reference']).is_file())
            self.assertTrue(module['evidence_requirements'])
            self.assertTrue(module['use_when'].strip())
            if module['availability'] == 'planning_only':
                self.assertIsNone(module['block_type'])
                self.assertIs(module['$defs']['input_schema'], False)
                self.assertIs(module['$defs']['frontend_schema'], False)

    def test_every_slot_resolves_to_catalog_with_text_fallback(self):
        self.assertEqual(read(self.templates['presentation_module_catalog']), self.catalog)
        entries = self.templates['templates'] + [self.templates['fallback']]
        rules = self.catalog['article_rules']
        self.assertLessEqual(set(rules), {e['type'] for e in entries})
        for entry in entries:
            template = read(Path('schemas') / entry['file'])
            rule = rules.get(entry['type'], {})
            self.assertLessEqual(set(rule), {'presentation_hints'})
            for slot_type in template['slots']:
                slot = read(Path('schemas/slots') / (slot_type + '.json'))
                with self.subTest(type=template['type'], slot=slot_type):
                    self.assertEqual(slot['type'], slot_type)
                    ids = slot['presentation_modules']
                    self.assertIsInstance(ids, list)
                    self.assertTrue(all(isinstance(name, str) for name in ids))
                    overrides = slot.get('presentation_conditions', {})
                    self.assertLessEqual(set(overrides), set(ids))
                    self.assertTrue(all(reason.strip() for reason in overrides.values()))
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertIn('text', ids)
                    self.assertTrue(set(ids) <= set(self.modules))

    def test_type_hints_reference_existing_roles_and_modules(self):
        for entry in self.templates['templates']:
            template = read(Path('schemas') / entry['file'])
            slots = {read(Path('schemas/slots') / (slot_type + '.json'))['id']
                     for slot_type in template['slots']}
            for hint in self.catalog['article_rules'].get(entry['type'], {}).get('presentation_hints', []):
                self.assertTrue(set(hint['roles']) <= slots)
                if 'preferred_component' in hint:
                    self.assertIn(hint['preferred_component'], self.modules)
                for module in hint.get('eligible_components', []):
                    self.assertEqual(self.modules[module]['availability'], 'supported')
                for option in hint.get('component_options', []):
                    self.assertEqual(self.modules[option['component']]['availability'], 'supported')
                self.assertIn(hint['fallback']['component'], self.modules)


if __name__ == '__main__':
    unittest.main()
