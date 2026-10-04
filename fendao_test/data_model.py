"""花舞（caimogu）作业接口的数据模型。

⚠️ 这个文件是照着 **线上真实返回** 写的，不要凭字段名想当然。
线上接口：https://www.caimogu.cc/gzlj/data?date=&lang=zh-cn

线上实际形状（2026-09-27 抓取核对）：

    {
      "status": 1,
      "data": [                       # ← 顶层就是**数组**，不是 {id: {...}} 字典
        {
          "id": "47",                 # ← 字符串，且是「boss 编号」不是作业编号
          "stage": 2,                 # ← 数字，阶段
          "rate": 1.6,
          "info": "【魔法】统治冰河地区...",
          "detail": [["等级", 60], ["生命值", 42000000], ...],   # ← 二元**数组**
          "part":   [{"name": "小狗1", "detail": [["生命值", 150000], ...]}],
          "homework": [
            {"id": 28107, "sn": "BT102", "unit": [1011, ...], "damage": 4200,
             "auto": 1, "remain": 0, "info": "",
             "video": [{"text": "...", "url": "...",
                        "image": [{"url": "...", "source": "..."}],  # ← 对象**数组**
                        "note": ""}]}
          ],
          "joyshow": []
        }
      ]
    }

历史坑（2026-09-27 修）：原来这份模型是与线上 **不匹配** 的 ——
`detail` / `part[].detail` 写成了 `List[DetailItem]`（要求对象），
`video[].image` 写成了 `List[str]`（要求字符串），
而线上给的是二元数组 / 对象数组。于是
`fendao_test.timeaxis:get_clanbattlework` 每次刷新都抛
`118 validation errors for HomeWorkData`，作业缓存**永远刷不进去**。
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Lenient(BaseModel):
    """公共基类：接口以后加字段不至于把解析打挂。"""

    model_config = ConfigDict(extra="ignore")


class DetailItem(_Lenient):
    """BOSS / 部位的一条属性。

    线上是 `["等级", 60]` 这种二元数组（不是 `{"name": ..., "value": ...}`），
    所以用 model_validator 在解析前把数组转成字典。
    """

    name: str
    value: int

    @model_validator(mode="before")
    @classmethod
    def _pair2dict(cls, v):
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return {"name": v[0], "value": v[1]}
        return v


class PartItem(_Lenient):
    """BOSS 的一个部位（如「小狗1」），属性形状同 DetailItem。"""

    name: str
    detail: List[DetailItem] = Field(default_factory=list)


class ImageItem(_Lenient):
    """作业视频里的配图。

    线上是 `{"url": ..., "source": ...}` 对象，不是字符串 URL。
    """

    url: str
    source: Optional[str] = None


class VideoItem(_Lenient):
    text: str = ""
    url: str = ""
    image: List[ImageItem] = Field(default_factory=list)
    note: str = ""


class HomeworkItem(_Lenient):
    """一条作业（一套阵容）。"""

    id: int = 0
    sn: str
    unit: List[int] = Field(default_factory=list)
    damage: int = 0
    auto: int = 0
    remain: int = 0
    info: str = ""
    video: List[VideoItem] = Field(default_factory=list)


class JoyshowItem(_Lenient):
    img: str = ""
    msg: str = ""
    width: int = 0
    height: int = 0


class DataItem(_Lenient):
    """一个 BOSS 的完整信息。

    注意 `id` 在线上是**字符串**（"47" / "25"），且它标识的是 BOSS，
    同一个 id 会以多条记录出现（每个 stage 一条）。
    """

    id: str
    stage: int
    rate: float = 0.0
    info: str = ""
    detail: List[DetailItem] = Field(default_factory=list)
    part: List[PartItem] = Field(default_factory=list)
    homework: List[HomeworkItem] = Field(default_factory=list)
    joyshow: List[JoyshowItem] = Field(default_factory=list)


class HomeWorkData(_Lenient):
    """接口顶层。`data` 是数组。"""

    status: int = 0
    data: List[DataItem] = Field(default_factory=list)


class VideoDictItem(_Lenient):
    """落盘用的扁平结构（json 里 video 的元素）。"""

    text: str = ""
    url: str = ""
    image: List[dict] = Field(default_factory=list)
    note: str = ""


class HomeWorkDictItem(_Lenient):
    """落盘用的一条作业。

    ⚠️ 键名必须与 `fendao_test/__init__.py` 的消费端一致：
    消费端读的是 `work["unit"]` / `work["damage"]` / `work["info"]` / `work["video"]`。
    历史坑：原来写入端用的是 `unit_id` / `video_link`，
    和消费端**对不上**，读出来就 KeyError。
    """

    unit: List[int] = Field(default_factory=list)
    damage: int = 0
    info: str = ""
    video: List[VideoDictItem] = Field(default_factory=list)
