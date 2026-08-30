from pydantic import BaseModel
from typing import List
from typing import TypedDict


class DetailItem(BaseModel):
    name: str
    value: int


class VideoItem(BaseModel):
    text: str
    url: str
    image: List[str]
    note: str


class HomeworkItem(BaseModel):
    id: int
    sn: str
    unit: List[int]
    damage: int
    auto: int
    remain: int
    info: str
    video: List[VideoItem]


class JoyshowItem(BaseModel):
    img: str
    msg: str
    width: int
    height: int


class DataItem(BaseModel):
    id: str
    stage: int
    rate: float
    info: str
    detail: List[DetailItem]
    part: List[str]
    homework: List[HomeworkItem]
    joyshow: List[JoyshowItem]


class HomeWorkData(BaseModel):
    status: int
    data: List[DataItem]


class VideoDictItem(TypedDict):
    text: str
    url: str
    image: List[str]
    note: str


class HomeWorkDictItem(TypedDict):
    unit: List[int]
    damage: int
    info: str
    video: List[VideoDictItem]
