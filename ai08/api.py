from functools import lru_cache
from fastapi import FastAPI,HTTPException,Depends
from .contracts import InferRequest,EventEnvelope,ReviewFeedback
from .service import AI08Service

app=FastAPI(title="AI-08 Backend",version="0.3.0")

@lru_cache
def get_service():
    return AI08Service()

@app.post("/v1/ai08/infer",response_model=list[EventEnvelope])
def infer(request:InferRequest,service:AI08Service=Depends(get_service)):
    try:
        return service.infer(request)
    except ValueError as error:
        raise HTTPException(status_code=422,detail=str(error)) from error

@app.post("/v1/ai08/review",response_model=EventEnvelope)
def review(feedback:ReviewFeedback,service:AI08Service=Depends(get_service)):
    try:
        return service.review(feedback)
    except KeyError as error:
        raise HTTPException(status_code=404,detail="event not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422,detail=str(error)) from error

@app.get("/v1/ai08/evaluation")
def evaluation(service:AI08Service=Depends(get_service)):
    return service.evaluate()

@app.get("/v1/ai08/events/{event_id}",response_model=EventEnvelope)
def event_by_id(event_id:str,service:AI08Service=Depends(get_service)):
    event=service.store.get(event_id)
    if event is None:
        raise HTTPException(status_code=404,detail="event not found")
    return event
