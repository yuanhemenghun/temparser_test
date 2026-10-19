import re

from string import templatelib
from typing import Callable, Self, Any, Literal
from types import GenericAlias


def inverse_t_string(template: templatelib.Template):
    return f"t'{''.join(
        ele if isinstance(ele, str) else f"{{{ele.expression}}}" for ele in template
    )}'"

def tranc_str(s: str, length: int, mode: Literal["after", "between"]) -> str:
    return s if len(s) < length else (s[:length] + "..." if mode == "after"
                                      else s[:length // 2] + "..." + s[-length // 2:])


class Parser[*Ts]:
    def __init__(self, template: templatelib.Template) -> None:
        if any(inter.value is None for inter in template.interpolations):
            raise TypeError("Parser模板中存在未插值的空洞None")
        self.template = template
        self._pattern = re.compile(
            "".join(re.escape(ele) if isinstance(ele, str) else r"(.+?)" for ele in template)
        )

    @staticmethod
    def _convert[T](interpolation: templatelib.Interpolation[Callable[[str], T]], s: str) -> T:
        if not callable(interpolation.value):
            raise TypeError(f"{type(interpolation.value).__name__}类型不可调用，"
                            "不能作为字符串Parser的参数")
        return interpolation.value(s)

    def parse(self, s: str) -> tuple[*Ts]:
        matched_list = self._pattern.fullmatch(s)
        if matched_list is None:
            raise ValueError(f"字符串无法被Parser的模板 {
                tranc_str(inverse_t_string(self.template), 40, "between")} 所解析，无效")
        return tuple(
            self._convert(inter, matched)
            for inter, matched in zip(self.template.interpolations, matched_list.groups())
        )


class _TypeDefaultParser[*Ts](GenericAlias):
    def __new__(cls, default_types: tuple[*Ts]) -> Self:
        return super().__new__(cls, parser, default_types)

    def __init__(self, default_types: tuple[*Ts]) -> None:
        self.default_types = default_types

    def __getattr__(self, name: str) -> Any:
        return object.__getattribute__(self, name)

    def __call__(self, template: templatelib.Template, s: str) -> tuple[*Ts]:
        if len(self.default_types) == len(template.interpolations):
            template = templatelib.Template(*(
                templatelib.Interpolation(
                    self.default_types[i // 2],
                    ele.expression,
                    ele.conversion,
                    ele.format_spec,
                )
                if isinstance(ele, templatelib.Interpolation) and ele.value is None
                else ele for i, ele in enumerate(template)
            ))
        return parser(template, s)


class parser[*Ts](tuple[*Ts]):
    def __new__(cls, template: templatelib.Template, s: str) -> tuple[*Ts]:
        return Parser[*Ts](template).parse(s)

    def __class_getitem__[*_Ts](cls, t: tuple[*_Ts]) -> _TypeDefaultParser[*_Ts]:
        return _TypeDefaultParser[*_Ts](t)


if __name__ == "__main__":
    def remove_percent(percent: str) -> float:
        return float(percent.rstrip("%")) / 100
    print(parser(
        t"aaa {int} bbb {remove_percent} ccc",
        "aaa 111 bbb 50% ccc"
    ))
    print(parser[int, float](
        t"aaa {int} bbb {remove_percent} ccc",
        "aaa 111 bbb 50% ccc"
    ))
    print(parser[int, float](
        t"aaa {None} bbb {None} ccc",
        "aaa 111 bbb 50 ccc"
    ))
