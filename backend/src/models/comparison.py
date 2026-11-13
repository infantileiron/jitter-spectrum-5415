from sqlalchemy import String,Double,Integer,JSON,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class ComparisonStudy(Base):
 __tablename__="comparison_studies"
 id:Mapped[str]=mapped_column(String,primary_key=True)
 name:Mapped[str]=mapped_column(String,unique=True)
 window_ids:Mapped[list]=mapped_column(JSON)
 detrend:Mapped[str]=mapped_column(String)
 min_frequency:Mapped[float]=mapped_column(Double)
 max_frequency:Mapped[float]=mapped_column(Double)
 frequency_points:Mapped[int]=mapped_column(Integer)
 created_at:Mapped[str]=mapped_column(String)
class ComparisonRun(Base):
 __tablename__="comparison_runs"
 id:Mapped[str]=mapped_column(String,primary_key=True)
 study_id:Mapped[str]=mapped_column(ForeignKey("comparison_studies.id"))
 status:Mapped[str]=mapped_column(String)
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default="")
 created_at:Mapped[str]=mapped_column(String)
