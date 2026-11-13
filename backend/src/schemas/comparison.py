from pydantic import BaseModel,Field,model_validator
from typing import Literal
class ComparisonStudyInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 window_ids:list[str]=Field(min_length=2,max_length=12)
 detrend:Literal["mean","linear"]="linear"
 min_frequency:float=Field(gt=0,le=10,allow_inf_nan=False)
 max_frequency:float=Field(gt=0,le=10,allow_inf_nan=False)
 frequency_points:int=Field(default=1200,ge=32,le=4000)
 @model_validator(mode="after")
 def range(self):
  if self.max_frequency<=self.min_frequency:raise ValueError("最高频率须高于最低频率")
  if len(set(self.window_ids))!=len(self.window_ids):raise ValueError("窗口不能重复选择")
  return self
class ComparisonRunInput(BaseModel):study_id:str
