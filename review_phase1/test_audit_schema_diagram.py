"""Integration tests on copies only; canonical artifacts must remain untouched."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'chỉnh sửa mới nhất - 01-10'
SCRIPT = BASE / 'tools' / 'audit_schema_diagram.py'

class AuditTests(unittest.TestCase):
    def test_real_bundle_read_only(self):
        files = [BASE / n for n in ('ontology_v1.0.ttl', 'shapes_v1.0.ttl', 'master_thesis_v1_synced_01-10.drawio.xml')]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('NOT CHECKED', proc.stdout)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in files])

    def run_mutation(self, old, new):
        source = BASE / 'master_thesis_v1_synced_01-10.drawio.xml'
        tree = ET.parse(source)
        matched = 0
        for diagram in tree.getroot().findall('diagram'):
            if not diagram.get('name', '').startswith('06-'):
                continue
            for cell in diagram.findall('.//mxCell'):
                value = cell.get('value', '')
                if old in value:
                    cell.set('value', value.replace(old, new))
                    matched += 1
        self.assertGreater(matched, 0, old)
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / 'mutated.xml'
            tree.write(copy, encoding='utf-8', xml_declaration=True)
            digest = hashlib.sha256(copy.read_bytes()).hexdigest()
            proc = subprocess.run([sys.executable, str(SCRIPT), '--drawio', str(copy)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(digest, hashlib.sha256(copy.read_bytes()).hexdigest())
            return proc

    def test_invalid_cardinality_syntax_is_not_silently_skipped(self):
        proc = self.run_mutation('candidateStock [1]', 'candidateStock [one]')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('Invalid cardinality', proc.stdout)

    def test_wrong_range_is_detected(self):
        proc = self.run_mutation('candidateStock [1]→ Stock', 'candidateStock [1]→ Company')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('Draw.io=Company', proc.stdout)

    def test_wrong_owner_is_detected(self):
        proc = self.run_mutation('EventStockCandidate —candidateStock', 'Company —candidateStock')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('domain differs', proc.stdout)

    def test_wrong_cardinality_is_detected(self):
        proc = self.run_mutation('candidateStock [1]', 'candidateStock [0..*]')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('cardinality: Draw.io=(0, None); SHACL=(1, 1)', proc.stdout)

    def test_unknown_datatype_property_is_detected(self):
        proc = self.run_mutation('candidateId, impactType', 'candidateTypo, impactType')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('candidateTypo: not an OWL DatatypeProperty', proc.stdout)
        self.assertIn('candidateId: MISSING', proc.stdout)

    def test_real_bundle_from_different_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = subprocess.run([sys.executable, str(SCRIPT), '--json'], cwd=directory, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

if __name__ == '__main__':
    unittest.main()
