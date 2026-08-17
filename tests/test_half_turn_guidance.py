from __future__ import annotations
import copy, json, unittest
from pathlib import Path
try:
    import jsonschema
except ImportError:
    jsonschema = None
from algorithms.slot_pose.half_turn_guidance import DEFAULT_CONFIG, build_guidance_result, run_manifest, validate_request_manifest, wrap_180_prefer_positive

def candidate(cid, angle, accepted=True, deficit=1400.0):
    return {"candidateId":cid,"centerDeg":angle,"halfWidthDeg":6.0,"prominence":140.0,"deficitArea":deficit,"accepted":accepted,"grooveScore":0.8 if accepted else 0.2,"rejectionReasons":[] if accepted else ["fixture_like"]}

def frame(char, items):
    raw=[{k:v for k,v in x.items() if k not in {"accepted","grooveScore","rejectionReasons"}} for x in items]
    assessments=[{"candidateId":x["candidateId"],"accepted":x["accepted"],"grooveScore":x["grooveScore"],"rejectionReasons":x["rejectionReasons"]} for x in items]
    accepted=[dict(x) for x in items if x["accepted"]]
    diagnostics={"rawCandidates":raw,"grooveRecognition":{"assessments":assessments},"grooveCandidates":accepted}
    if len(accepted)==1: diagnostics["singleGroovePose"]={"geometryValid":True,"role":{"candidateId":accepted[0]["candidateId"]},"imageMeasurement":{"profileAzimuthXRightClockwiseDeg":accepted[0]["centerDeg"]}}
    return {"schemaVersion":"slot-pose-result/3","image":{"sha256":char*64},"result":{"valid":len(accepted)==1},"error":None if len(accepted)==1 else {"code":"GROOVE_RECOGNITION_FAILED"},"diagnostics":diagnostics}

def request(mode="HALF_TURN_PAIR"):
    captures=[{"captureIndex":1,"relativePath":"A2/1.bmp","imageSha256":"a"*64}]
    half=None
    if mode=="HALF_TURN_PAIR":
        captures.append({"captureIndex":2,"relativePath":"A2/2.bmp","imageSha256":"b"*64})
        half={"nominalRotationDeg":180.0,"directionRequired":False,"executionResponsibility":"EXTERNAL_HARDWARE","conventionId":"image-x-right-y-down-clockwise/1"}
    return {"requestId":"r1","sampleId":"part-1","mode":mode,"captures":captures,"halfTurn":half}

def enabled():
    value=copy.deepcopy(DEFAULT_CONFIG); value["enabled"]=True; return value

class HalfTurnGuidanceTests(unittest.TestCase):
    def test_direction_independent_half_turn_and_positive_tie(self):
        self.assertEqual((20+180)%360,(20-180)%360)
        self.assertEqual(180.0,wrap_180_prefer_positive(180))

    def test_manifest_has_two_explicit_formats_and_rejects_direction(self):
        for mode in ("SINGLE_CAPTURE","HALF_TURN_PAIR"):
            validate_request_manifest({"schemaVersion":"half-turn-guidance-request/1","datasetId":"x","requests":[request(mode)]})
        broken=request(); broken["halfTurn"]["directionRequired"]=True
        with self.assertRaisesRegex(ValueError,"direction-independent"): validate_request_manifest({"schemaVersion":"half-turn-guidance-request/1","datasetId":"x","requests":[broken]})

    def test_default_disabled_is_fail_closed(self):
        result=build_guidance_result(request("SINGLE_CAPTURE"),{"a"*64:frame("a",[candidate("g",120)])},DEFAULT_CONFIG)
        self.assertFalse(result["valid"]); self.assertEqual("EXPERIMENT_DISABLED",result["status"]); self.assertIsNone(result["correctionDeg"]); self.assertIsNone(result["plcExecution"])

    def test_single_image_outputs_same_adjustment_formula(self):
        result=build_guidance_result(request("SINGLE_CAPTURE"),{"a"*64:frame("a",[candidate("g",112.834)])},enabled())
        self.assertTrue(result["valid"]); self.assertAlmostEqual(22.834,result["currentAngleDeg"]); self.assertAlmostEqual(62.166,result["correctionDeg"]); self.assertEqual("CLOCKWISE",result["rotationDirection"])
        self.assertEqual("NOT_APPLICABLE",result["realPairValidationStatus"])

    def test_versioned_effective_adjudication_is_respected_without_hiding_original_rejection(self):
        payload=frame("a",[candidate("g",119.57839392492804)])
        payload["diagnostics"]["grooveSourceConsistency"]={"status":"rejected"}
        payload["diagnostics"]["sidewallSourceConsistencyAdjudication"]={
            "schemaVersion":"source-consistency-adjudication/1","decision":"ACCEPTED_OVERRIDE",
            "effectiveStatus":"accepted","imagePoseReleaseAllowed":True,"manualTruthAppliedAtRuntime":False,
        }
        result=build_guidance_result(request("SINGLE_CAPTURE"),{"a"*64:payload},enabled())
        self.assertTrue(result["valid"]); self.assertAlmostEqual(29.57839392492804,result["currentAngleDeg"])
        item=result["captures"][0]["candidates"][0]
        self.assertEqual("VERSIONED_SOURCE_CONSISTENCY_ADJUDICATION",item["effectiveUsabilitySource"])
        self.assertIn("source_consistency_rejected",item["originalRejectionReasonsRetained"])

    def test_dead_zone_boundaries_and_exact_antipode(self):
        for current in (80.0,90.0):
            result=build_guidance_result(request("SINGLE_CAPTURE"),{"a"*64:frame("a",[candidate("g",current+90)])},enabled())
            self.assertEqual(0.0,result["correctionDeg"]); self.assertEqual("NONE",result["rotationDirection"])
        tie=build_guidance_result(request("SINGLE_CAPTURE"),{"a"*64:frame("a",[candidate("g",355)])},enabled())
        self.assertEqual(180.0,tie["correctionDeg"]); self.assertEqual("CLOCKWISE",tie["rotationDirection"])

    def test_both_valid_use_second_direct_not_average(self):
        first=frame("a",[candidate("g1",110.0)]); second=frame("b",[candidate("g2",292.0)])
        result=build_guidance_result(request(),{"a"*64:first,"b"*64:second},enabled())
        self.assertTrue(result["valid"]); self.assertEqual("CAPTURE_2_DIRECT",result["measurementSource"]); self.assertAlmostEqual(-158.0,result["currentAngleDeg"]); self.assertAlmostEqual(-117.0,result["correctionDeg"])
        self.assertAlmostEqual(2.0,result["selectedMatch"]["angularResidualDeg"])
        self.assertEqual("MISSING",result["realPairValidationStatus"])

    def test_only_first_valid_propagates_and_only_second_is_direct(self):
        first_only=build_guidance_result(request(),{"a"*64:frame("a",[candidate("g1",110)]),"b"*64:frame("b",[candidate("g2",290,False)])},enabled())
        self.assertEqual("CAPTURE_1_PROPAGATED_HALF_TURN",first_only["measurementSource"]); self.assertAlmostEqual(-160,first_only["currentAngleDeg"])
        second_only=build_guidance_result(request(),{"a"*64:frame("a",[candidate("g1",110,False)]),"b"*64:frame("b",[candidate("g2",290)])},enabled())
        self.assertEqual("CAPTURE_2_DIRECT",second_only["measurementSource"]); self.assertAlmostEqual(-160,second_only["currentAngleDeg"])

    def test_stationary_fixture_does_not_verify_as_rotating_groove(self):
        result=build_guidance_result(request(),{"a"*64:frame("a",[candidate("shadow1",31,False)]),"b"*64:frame("b",[candidate("shadow2",31,False)])},enabled())
        self.assertFalse(result["valid"]); self.assertEqual("PAIR_EVIDENCE_INCONSISTENT",result["error"]["code"]); self.assertIsNone(result["correctionDeg"])

    def test_single_failure_preserves_upstream_root_error(self):
        payload=frame("a",[]); payload["error"]={"code":"HOUSING_CIRCLE_NOT_FOUND"}
        result=build_guidance_result(request("SINGLE_CAPTURE"),{"a"*64:payload},enabled())
        self.assertFalse(result["valid"]); self.assertEqual("HOUSING_CIRCLE_NOT_FOUND",result["error"]["code"])
        self.assertIsNone(result["correctionDeg"])

    def test_one_real_one_shadow_keeps_evidence_and_uses_real(self):
        first=frame("a",[candidate("real",110),candidate("shadow-a",31,False,300)])
        second=frame("b",[candidate("blocked-real",290,False),candidate("shadow-b",31,False,300)])
        result=build_guidance_result(request(),{"a"*64:first,"b"*64:second},enabled())
        self.assertTrue(result["valid"]); self.assertEqual("CAPTURE_1_PROPAGATED_HALF_TURN",result["measurementSource"])
        self.assertEqual(2,len(result["captures"][1]["candidates"]))

    def test_shape_mismatch_cannot_be_selected_by_angle_alone(self):
        first=frame("a",[candidate("g1",110,deficit=1400)])
        second=frame("b",[candidate("g2",290,deficit=200)])
        result=build_guidance_result(request(),{"a"*64:first,"b"*64:second},enabled())
        self.assertFalse(result["valid"]); self.assertEqual("PAIR_EVIDENCE_INCONSISTENT",result["error"]["code"])
        self.assertIn("deficit_area_difference",result["hypotheses"][0]["failedChecks"])

    def test_ambiguous_eligible_matches_fail_closed(self):
        first=frame("a",[candidate("a1",110),candidate("a2",110.5)])
        second=frame("b",[candidate("b1",290)])
        result=build_guidance_result(request(),{"a"*64:first,"b"*64:second},enabled())
        self.assertFalse(result["valid"]); self.assertEqual("PAIR_MATCH_AMBIGUOUS",result["error"]["code"]); self.assertIsNone(result["rotationDirection"])

    @unittest.skipIf(jsonschema is None,"jsonschema unavailable")
    def test_contract_schemas_accept_outputs(self):
        root=Path(__file__).resolve().parents[1]/"contracts"
        for name in ("half-turn-guidance-config.schema.json","half-turn-guidance-request.schema.json","half-turn-guidance-result.schema.json"):
            jsonschema.Draft202012Validator.check_schema(json.loads((root/name).read_text()))
        manifest={"schemaVersion":"half-turn-guidance-request/1","datasetId":"x","requests":[request()]}
        jsonschema.validate(manifest,json.loads((root/"half-turn-guidance-request.schema.json").read_text()))
        outputs=run_manifest(manifest,{"a"*64:frame("a",[candidate("g",110)]),"b"*64:frame("b",[candidate("g2",290)])},enabled())
        validator=jsonschema.Draft202012Validator(json.loads((root/"half-turn-guidance-result.schema.json").read_text()))
        for output in outputs: validator.validate(output)

if __name__=="__main__": unittest.main()
