"""Independent exact diagnostic v1 package and measurement-contract audit."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/"runtime/pipeline/scenario_pipeline"))
from worker_exchange.measurement_contract import validate,verify_report

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def main():
    summary=read(HERE/"package-probes-summary.json")
    manifest=read(HERE/"draft-execution-manifest.json")
    plan=read(HERE/"case-plan.json")
    assert summary["passed"] is True and summary["candidates"]==24
    assert summary["synthetic"] is True and summary["selected"] is False
    assert len(summary["records"])==24
    by_case={e["case_id"]:e for e in manifest["cases"]}
    distances={}
    negative_logs=[]
    for record in summary["records"]:
        feet=record["feet"];candidate=record["candidate_id"]
        receipt_path=HERE/record["receipt"]
        assert sha(receipt_path)==record["receipt_sha256"]
        assert sha(HERE/record["log"])==record["log_sha256"]
        receipt=read(receipt_path)
        case=receipt["case_id"];entry=by_case[case]
        assert case.endswith("__"+str(feet)) and receipt["candidate_id"]==candidate
        assert receipt["positive"]["passed"] is True
        assert receipt["positive"]["candidate_id"]==candidate
        assert set(receipt["positive"]["checks"])=={
            "actual_analysis","native_validation","mandatory_observations",
            "lean_decoder","render","final_decode","acquisition_unchanged"}
        assert receipt["positive"]["construction_sha256"]==record["construction_sha256"]
        output=Path(receipt["scratch"])/"output"
        assert output.is_dir() and (output/"compatibility.json").is_file()
        assert read(output/"compatibility.json")["passed"] is True
        contract=read(HERE/entry["measurement_contract"])
        validate(contract,plan["requirement_dispositions"],(output/"finalize.py").read_text(),case)
        measurements=verify_report(contract,read(output/"analysis-report.json"),output)
        assert set(measurements)=={"continuous_signal_distance_ft","weather_context",
            "other_area_coverage","other_area_duplicate"}
        value=measurements["continuous_signal_distance_ft"]["value"]
        assert abs(value-feet)<.5
        assert measurements["weather_context"]["value"]=="clear_noon"
        result=read(output/"result.json")
        assert result["case_id"]==case and result["accepted"] is False
        assert result["provenance_kind"]=="synthetic_cpu_fixture"
        assert result["legal_verdict_claimed"] is False
        distances[(feet,candidate)]=value
        negative=Path(receipt["scratch"])/"negative"
        assert not (negative/"native_samples.jsonl").exists()
        command=[sys.executable,str(negative/"finalize.py"),"--attempt",str(negative),
            "--output",str(negative/"repeat-negative-analysis.json")]
        environment=dict(os.environ)
        environment["PYTHONPATH"]=os.pathsep.join((str(ROOT/"runtime/pipeline"),
            str(ROOT/"runtime/pipeline/scenario_pipeline"),environment.get("PYTHONPATH","")))
        failure=subprocess.run(command,cwd=negative,env=environment,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
        assert failure.returncode!=0 and contract["negative"]["error_contains"] in failure.stdout
        log=HERE/f"package-probe-{feet}-{candidate}-negative-audit.log"
        log.write_text(failure.stdout)
        negative_logs.append({"feet":feet,"candidate_id":candidate,"sha256":sha(log)})
    for candidate in ("primary","fallback1","fallback2","fallback3"):
        assert distances[(90,candidate)]<distances[(100,candidate)]<distances[(110,candidate)]
        assert distances[(290,candidate)]<distances[(300,candidate)]<distances[(310,candidate)]
    audit={"format":"c104393-independent-package-audit-v1","passed":True,
        "cases":6,"positive":24,"negative":24,"measurement_contracts":6,
        "synthetic":True,"selected":False,"native_executed":False,
        "measured_distances_ft":{str(feet):distances[(feet,"primary")]
            for feet in (90,100,110,290,300,310)},
        "summary_sha256":sha(HERE/"package-probes-summary.json"),
        "negative_logs":negative_logs}
    (HERE/"independent-package-audit.json").write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps({k:v for k,v in audit.items() if k!="negative_logs"},indent=2))

if __name__=="__main__":main()
