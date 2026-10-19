"""Evidence/checkpoint contract fixtures; not semantic LLM-quality evidence."""
import pytest
from backend import review_script
from backend.analysis import validate_items


def test_hierarchical_resume_retains_original_evidence(monkeypatch):
    evidence={f'e{i}':{'type':'transcript','start_ms':i*1000,'end_ms':i*1000+900,'text':f'fact {i}'} for i in range(21)}
    saved={'evidence':evidence,'items':[{'text':v['text'],'evidence_ids':[key],'source_ranges':[{k:v[k] for k in ('type','start_ms','end_ms')}]} for key,v in evidence.items()]}
    calls=[]
    def chat(provider,messages,**kwargs):
        import json
        body=json.loads(messages[1]['content']);calls.append(list(body['evidence']))
        if len(calls)==2:raise RuntimeError('controlled interruption')
        return {'items':[{'text':'Grounded fixture summary','evidence_ids':list(body['evidence']),'section':'hook','claim_type':'fact'}]}
    monkeypatch.setattr(review_script,'chat_json',chat)
    payload={'mode':'review','language':'en','provider':{}}
    with pytest.raises(RuntimeError):review_script.reduce(saved,payload,[1,2],lambda *_:None,validate_items)
    assert saved['reduction']['next']==1
    review_script.reduce(saved,payload,[1,2],lambda *_:None,validate_items)
    assert len(calls)==4  # failed second group retries; completed first group does not.
    assert saved['reduction_done']
    assert set(saved['items'][0]['evidence_ids'])==set(evidence)
    assert {r['start_ms'] for r in saved['items'][0]['source_ranges']}==set(range(0,21000,1000))
