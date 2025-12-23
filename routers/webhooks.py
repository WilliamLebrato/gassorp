from fastapi import APIRouter, HTTPException, Request
from models import WakeWebhook
from services.lifecycle import LifecycleManager

router = APIRouter(prefix="/api/webhook", tags=["webhooks"])

lifecycle_mgr: LifecycleManager = None


def set_lifecycle_manager(lmgr: LifecycleManager):
    global lifecycle_mgr
    lifecycle_mgr = lmgr


@router.post("/wake")
async def wake_webhook(payload: WakeWebhook, request: Request):
    if not lifecycle_mgr:
        raise HTTPException(status_code=503, detail="Lifecycle manager not initialized")
    
    success = await lifecycle_mgr.wake_on_webhook(payload.server_id, payload.token)
    
    if success:
        return {"status": "ok", "message": "Wake signal received"}
    else:
        raise HTTPException(status_code=400, detail="Wake failed")
