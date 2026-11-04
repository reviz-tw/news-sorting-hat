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
        self.modules = {m['id']: m for m in self.catalog['modules']}

    def test_supported_modules_match_output_contract(self):
        variants = read('schemas/presentation.schema.json')['properties']['blocks']['items']['oneOf']
        block_types = {v['properties']['type']['const'] for v in variants}
        self.assertEqual(len(self.modules), len(self.catalog['modules']))
        supported = {m['block_type'] for m in self.modules.values() if m['availability'] == 'supported'}
        self.assertEqual(supported, block_types)
        for module in self.modules.values():
            self.assertIn(module['availability'], ('supported', 'planning_only'))
            self.assertTrue((ROOT / module['reference']).is_file())
            self.assertTrue(module['evidence_requirements'])
            if module['availability'] == 'planning_only':
                self.assertIsNone(module['block_type'])
                self.assertNotIn(module['id'], block_types)

    def test_every_slot_resolves_to_catalog_with_text_fallback(self):
        self.assertEqual(read(self.templates['presentation_module_catalog']), self.catalog)
        for template in self.templates['templates'] + [self.templates['fallback']]:
            for slot in template['slots']:
                with self.subTest(type=template['type'], slot=slot['id']):
                    candidates = slot['presentation_modules']
                    ids = [m['module_id'] for m in candidates]
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertIn('text', ids)
                    self.assertTrue(set(ids) <= set(self.modules))
                    self.assertTrue(all(m['use_when'].strip() for m in candidates))

    def test_type_hints_reference_existing_roles_and_modules(self):
        for template in self.templates['templates']:
            slots = {s['id'] for s in template['slots']}
            for hint in template.get('presentation_hints', []):
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
