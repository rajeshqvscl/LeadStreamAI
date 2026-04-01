from fastapi import APIRouter, HTTPException, Header, Depends
from typing import List, Optional
from pydantic import BaseModel
from app.models.prompt import get_all_prompts, create_prompt, update_prompt, delete_prompt

router = APIRouter()

class PromptBase(BaseModel):
    name: str
    prompt_type: str
    content: str
    description: Optional[str] = None
    is_active: Optional[bool] = True

class PromptUpdate(BaseModel):
    name: Optional[str] = None
    prompt_type: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/prompts")
def list_prompts():
    return get_all_prompts()

@router.post("/prompts")
def add_prompt(prompt: PromptBase):
    prompt_id = create_prompt(
        prompt.name, 
        prompt.prompt_type, 
        prompt.content, 
        prompt.description, 
        prompt.is_active
    )
    return {"id": prompt_id, "message": "Prompt created successfully"}

@router.put("/prompts/{prompt_id}")
def edit_prompt(prompt_id: int, prompt_data: PromptUpdate):
    success = update_prompt(prompt_id, prompt_data.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt updated successfully"}

@router.delete("/prompts/{prompt_id}")
def remove_prompt(prompt_id: int):
    success = delete_prompt(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt deleted successfully"}
