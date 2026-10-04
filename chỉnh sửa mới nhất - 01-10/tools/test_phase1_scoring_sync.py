"""Phase 1 specification synchronization checks; no RDF or pipeline claim."""
from decimal import Decimal
import hashlib,json,re,unittest,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
PKG=Path(__file__).resolve().parent.parent
EXPECTED={"DIRECT":"1.0","INDIRECT_INDUSTRY":"0.5","INDIRECT_SUBSIDIARY":"0.5","INDIRECT_LEADERSHIP":"0.5"}
ROUTE="T=relationStrength: DIRECT=1.0; INDIRECT_INDUSTRY=0.5; INDIRECT_SUBSIDIARY=0.5; INDIRECT_LEADERSHIP=0.5"
FIXTURE="tools/news_fixture_2026-10-01_hdbank_dividend/"
HIST=PKG/"tools/verification_contract_1.0.5.json"
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def report_text():
 path=PKG/"Bao_cao_Phase_1_Ontology_WFKG_ban_chot_da_dong_bo_hieu_dinh.docx"
 with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read("word/document.xml"))
 ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
 return "\n".join("".join(x.text or "" for x in para.findall(".//w:t",ns)) for para in root.findall(".//w:body//w:p",ns))
class Phase1ScoringSyncTests(unittest.TestCase):
 def test_scoring_spec_route_values(self):
  s=(PKG/"SCORING_SPEC.md").read_text(encoding="utf-8").split("## 8. Relation strength",1)[1].split("\n## ",1)[0]
  for route,value in EXPECTED.items():self.assertRegex(s,rf"\|\s*{route}\s*\|\s*{re.escape(value)}\s*\|")
 def test_no_stale_universal_T_claims(self):
  s=(PKG/"SCORING_SPEC.md").read_text(encoding="utf-8")
  self.assertIn("T=1.0` với DIRECT và `T=0.5` với cả ba INDIRECT route",s)
  self.assertIn("T theo giá trị baseline riêng của route",s)
  self.assertIn("T khớp bảng bốn route tại §8",s)
  p=(PKG/"EVALUATION_PROTOCOL.md").read_text(encoding="utf-8")
  self.assertIn("route-strength values are explicitly preserved",p)
  self.assertNotIn("Legacy 1.0.4 strength/fallback policies",p)
 def test_core_specs_separate_S_R_T(self):
  for name in ("SCORING_SPEC.md","EVENT_SCHEMA.md","ANNOTATION_GUIDELINE.md","EVALUATION_PROTOCOL.md","PHASE1_ACCEPTANCE.md"):
   s=(PKG/name).read_text(encoding="utf-8");self.assertIn("relationStrength",s,name);self.assertIn("0.5",s,name)
  s=(PKG/"SCORING_SPEC.md").read_text(encoding="utf-8")
  self.assertIn("sourceConfidence",s);self.assertIn("relationConfidence",s)
 def test_word_route_map_and_fallback_removal(self):
  s=report_text();self.assertIn(ROUTE,s);self.assertIn("SCORING_SPEC.md 1.1.0",s)
  self.assertNotIn("chưa calibrated dùng fallback 0,5",s)
  self.assertNotIn("calibrated score hoặc fallback 0,5",s)
 def test_drawio_route_map_version_and_geometry(self):
  root=ET.parse(PKG/"master_thesis_v1_synced_01-10.drawio").getroot()
  cells={x.get("id"):x for x in root.findall(".//mxCell")}
  score=cells["weTA0hvWxfCujyoZNfAk-11"];text=score.get("value","")
  for route,value in EXPECTED.items():self.assertIn(route+"="+value,text)
  self.assertIn("spec 1.1.0",text);self.assertIn("S/R/T are distinct",text)
  self.assertIn("structural contract 1.0.5",cells["mZ28CVNe_N0uJWWchiWa-45"].get("value",""))
  page=next(x for x in root.findall("diagram") if x.get("name","").startswith("05-"))
  geom=score.find("mxGeometry")
  self.assertLessEqual(float(geom.get("y"))+float(geom.get("height")),int(page.find("mxGraphModel").get("pageHeight")))
 def test_phase2_variant_only_changes_industry_T(self):
  s=(PKG/"EVALUATION_PROTOCOL.md").read_text(encoding="utf-8")
  self.assertIn("change only INDUSTRY T from V1's 0.5",s)
  self.assertIn("DIRECT T=1.0 and both other INDIRECT T=0.5",s)
  self.assertIn("separately versioned Phase 2 research experiment",s)
 def test_decimal_control_is_not_fixture_data(self):
  S,A,L,R=map(Decimal,("0.5","0.8","1.0","0.5"));confidence=(S+A+L+R)/Decimal(4)
  self.assertEqual(confidence,Decimal("0.7"))
  self.assertEqual(confidence*Decimal(EXPECTED["DIRECT"]),Decimal("0.70"))
  self.assertEqual(confidence*Decimal(EXPECTED["INDIRECT_INDUSTRY"]),Decimal("0.35"))
 def test_hdbank_payload_unchanged_against_recorded_hashes(self):
  expected=json.loads(HIST.read_text(encoding="utf-8"))["artifacts_sha256"]
  for name in ("data.ttl","queries.rq","expected.json","run_checks.py","TEST_PLAN.md"):
   rel=FIXTURE+name;self.assertIn(rel,expected);self.assertEqual(digest(PKG/rel),expected[rel],rel)
  self.assertIn("TEST_PLAN.md",(PKG/FIXTURE/"data.ttl").read_text(encoding="utf-8"))
 def test_doc_versions_and_pdf_gate(self):
  for name in ("SCORING_SPEC.md","EVENT_SCHEMA.md","ANNOTATION_GUIDELINE.md","EVALUATION_PROTOCOL.md","PHASE1_ACCEPTANCE.md"):
   self.assertIn("Document version: 1.1.0",(PKG/name).read_text(encoding="utf-8"),name)
  self.assertIn("PENDING_RDF_VALIDATION_AND_CURRENT_PDF_EXPORT",(PKG/"tools/phase1_package_manifest_1.1.0.json").read_text(encoding="utf-8"))
 def test_manifest_hashes_match_payloads(self):
  manifest_path="tools/phase1_package_manifest_1.1.0.json"
  data=json.loads((PKG/manifest_path).read_text(encoding="utf-8"))
  self.assertIn(manifest_path,data["submission_files"])
  self.assertNotIn(manifest_path,data["sha256"])
  for rel in data["submission_files"]:
   path=PKG/rel
   self.assertTrue(path.is_file(),rel)
   if rel != manifest_path:
    self.assertEqual(digest(path),data["sha256"].get(rel),rel)
if __name__=="__main__":unittest.main(verbosity=2)
