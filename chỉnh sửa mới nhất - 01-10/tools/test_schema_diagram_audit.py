"""Role-semantic regression tests; mutate XML in memory, never canonical files."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('schema_audit', BASE / 'tools/audit_schema_diagram.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
DRAWIO = BASE / 'master_thesis_v1_synced_01-10.drawio'
OWNER = '2411blnfpnkDnIr3tklR-3'
PARENT = '2411blnfpnkDnIr3tklR-5'
CHILD = 'R3vZ3JpwLF3V6DxzlldD-2'


class SubsidiaryRoleAuditTests(unittest.TestCase):
    def tree(self):
        return ET.parse(DRAWIO)

    def cells(self, tree):
        tab = next(d for d in tree.getroot().findall('diagram')
                   if d.get('name', '').startswith('00-'))
        return {c.get('id'): c for c in tab.findall('.//mxCell')}

    def report(self, tree):
        with patch.object(audit_module.ET, 'parse', return_value=tree):
            return audit_module.audit(BASE / 'ontology_v1.0.ttl',
                                      BASE / 'shapes_v1.0.ttl', DRAWIO)

    def role_rows(self, report):
        return [r for r in report['results'] if 'subsidiary-owner-role' in r['where']]

    def test_wrong_child_owner_is_rejected_even_when_both_are_company(self):
        tree = self.tree()
        cells = self.cells(tree)
        cells[OWNER].set('source', CHILD)
        cells[CHILD].set('value', 'Company')
        cells[PARENT].set('value', 'Company')
        rows = self.role_rows(self.report(tree))
        self.assertEqual([r['status'] for r in rows], ['FAIL'], rows)
        self.assertIn('parentCompany target', rows[0]['message'])

    def test_canonical_parent_owns_subsidiary_relation(self):
        rows = self.role_rows(self.report(self.tree()))
        self.assertEqual([r['status'] for r in rows], ['PASS'], rows)

    def test_missing_parent_connector_is_not_a_vacuous_pass(self):
        tree = self.tree()
        self.cells(tree)['2411blnfpnkDnIr3tklR-8'].set('value', '')
        self.assertEqual([r['status'] for r in self.role_rows(self.report(tree))], ['FAIL'])

    def test_parent_connector_must_belong_to_same_relation(self):
        tree = self.tree()
        self.cells(tree)['2411blnfpnkDnIr3tklR-6'].set('source', CHILD)
        self.assertEqual([r['status'] for r in self.role_rows(self.report(tree))], ['FAIL'])

    def test_xml_keeps_seven_editable_pages_and_valid_references(self):
        root = self.tree().getroot()
        tabs = root.findall('diagram')
        self.assertEqual(len(tabs), 7)
        self.assertEqual(len({d.get('id') for d in tabs}), 7)
        for tab in tabs:
            self.assertIsNotNone(tab.find('mxGraphModel'))
            cells = tab.findall('.//mxCell')
            ids = [c.get('id') for c in cells]
            self.assertNotIn(None, ids)
            self.assertEqual(len(ids), len(set(ids)))
            for cell in cells:
                for attr in ('parent', 'source', 'target'):
                    if cell.get(attr) is not None:
                        self.assertIn(cell.get(attr), ids)

    def values(self):
        return {c.get('id'): audit_module.label_text(c.get('value', ''))
                for c in self.tree().getroot().findall('.//mxCell')}

    def test_event_entity_edge_excludes_datatype_and_names_govorg(self):
        values = self.values()
        self.assertNotIn('availableAt', values['_DqDvpdGpuATSC4ekHHC-11'])
        self.assertIn('issuedBy', values['_DqDvpdGpuATSC4ekHHC-11'])
        self.assertIn('GovOrg', values['_DqDvpdGpuATSC4ekHHC-7'])
        self.assertIn('availableAt', values['_DqDvpdGpuATSC4ekHHC-14'])

    def test_alias_string_and_stock_uri_remain_distinct(self):
        values = self.values()
        self.assertNotIn('hasAlias', values['A1VN0XJZ2zYTKMQ9EYZ1-9'])
        self.assertIn('“TCB”', values['A1VN0XJZ2zYTKMQ9EYZ1-7'])
        self.assertIn('alias', values['A1VN0XJZ2zYTKMQ9EYZ1-7'])
        self.assertIn('Stock URI', values['A1VN0XJZ2zYTKMQ9EYZ1-7'])

    def test_baseline_note_does_not_replace_reaction_cutoff(self):
        values = self.values()
        self.assertIn('inferenceCutoff = Event.availableAt', values['mZ28CVNe_N0uJWWchiWa-45'])
        self.assertIn('generatedAt', values['mZ28CVNe_N0uJWWchiWa-45'])
        self.assertIn('1.0.4', values['weTA0hvWxfCujyoZNfAk-11'])
        self.assertIn('observation.availableAt ≤ Reaction.availableAt', values['mZ28CVNe_N0uJWWchiWa-32'])


if __name__ == '__main__':
    unittest.main()
