import re

from string import templatelib
from typing import Callable, Self, Any, Unpack, Literal, get_origin, get_args, overload
from types import GenericAlias


def inverse_t_string(template: templatelib.Template):
    return f"t'{''.join(
        ele if isinstance(ele, str) else f"{{{ele.expression}}}" for ele in template
    )}'"

def tranc_str(s: str, length: int, mode: Literal["after", "between"]) -> str:
    return s if len(s) < length else (
        s[:length] + "..." if mode == "after"
        else s[:length // 2] + "..." + s[-length // 2:]
    )

@overload
def make_tuple[*Ts](t: tuple[*Ts]) -> tuple[*Ts]: ...
@overload
def make_tuple[T](t: T) -> tuple[T]: ...
def make_tuple[*Ts, T](t: tuple[*Ts] | T) -> tuple[*Ts] | tuple[T]:
    return t if isinstance(t, tuple) else (t,)


class Parser[*Ts]:
    def __init__(self, template: templatelib.Template) -> None:
        if any(self.is_empty_interp(interp) for interp in template.interpolations):
            raise ValueError("Parser模板中存在未插值的空洞")
        self.template = template
        self._pattern = re.compile(
            "".join(re.escape(ele) if isinstance(ele, str) else r"(.+?)" for ele in template)
        )

    @staticmethod
    def _convert[T](interp: templatelib.Interpolation[Callable[[str], T]], s: str) -> T:
        if not callable(interp.value):
            raise TypeError(f"{type(interp.value).__name__}类型不可调用，"
                            "不能作为字符串Parser的参数")
        return interp.value(s)

    @staticmethod
    def is_empty_interp(interp: templatelib.Interpolation[Any]) -> bool:
        return interp.value is None

    def parse(self, s: str) -> tuple[*Ts]:
        matched_list = self._pattern.fullmatch(s)
        if matched_list is None:
            raise ValueError("字符串无法被Parser的模板"
                f"{tranc_str(inverse_t_string(self.template), 40, "between")} 所解析，无效")
        return tuple(
            self._convert(interp, matched)
            for interp, matched in zip(self.template.interpolations, matched_list.groups())
        )

    def __class_getitem__[*_Ts](cls, t: tuple[*_Ts]) -> _DefaultParserBound[*_Ts]:
        return _DefaultParserBound(make_tuple(t))


class _DefaultParser[*Ts]:
    def __init__(self, default_types: tuple[*Ts]) -> None:
        self.default_types = default_types

    def __getattr__(self, name: str) -> Any:
        return object.__getattribute__(self, name)

    def _fill_empty_interps(self, template: templatelib.Template) -> templatelib.Template:
        default_types = self.default_types

        if len(default_types) == 1:
            t = default_types[0]
            if isinstance(t, GenericAlias) and t.__unpacked__:
                default_types = t.__args__
            elif get_origin(t) is Unpack and isinstance((t := get_args(t)[0]), GenericAlias):
                default_types = t.__args__

        if len(default_types) == 2 and default_types[-1] == ...:
            default_types = (default_types[0],) * len(template.interpolations)

        if len(default_types) == len(template.interpolations):
            template = templatelib.Template(*(
                templatelib.Interpolation(
                    default_types[i // 2],
                    ele.expression,
                    ele.conversion,
                    ele.format_spec,
                )
                if isinstance(ele, templatelib.Interpolation) and Parser.is_empty_interp(ele)
                else ele for i, ele in enumerate(template)
            ))

        return template


class _DefaultParserBound[*Ts](_DefaultParser[*Ts], GenericAlias):
    def __new__(cls, default_types: tuple[*Ts]) -> Self:
        return super().__new__(cls, Parser, default_types)

    def __call__(self, template: templatelib.Template) -> Parser[*Ts]:
        template = self._fill_empty_interps(template)
        return Parser(template)

class _DefaultParserUnbound[*Ts](_DefaultParser[*Ts], GenericAlias):
    def __new__(cls, default_types: tuple[*Ts]) -> Self:
        return super().__new__(cls, parse, default_types)

    def __call__(self, template: templatelib.Template, s: str) -> tuple[*Ts]:
        template = self._fill_empty_interps(template)
        return parse(template, s)


class parse[*Ts](tuple[*Ts]):
    def __new__(cls, template: templatelib.Template, s: str) -> tuple[*Ts]:
        return Parser[*Ts](template).parse(s)

    def __class_getitem__[*_Ts](cls, t: tuple[*_Ts]) -> _DefaultParserUnbound[*_Ts]:
        return _DefaultParserUnbound(make_tuple(t))


if __name__ == "__main__":
    def remove_percent(percent: str) -> float:
        return float(percent.rstrip("%")) / 100

    print(parse(
        t"aaa {int} bbb {remove_percent} ccc",
        "aaa 111 bbb 50% ccc"
    ))
    print(Parser(
        t"aaa {int} bbb {remove_percent} ccc",
    ).parse("aaa 111 bbb 50% ccc"))

    print(parse[int, float](
        t"aaa {int} bbb {remove_percent} ccc",
        "aaa 111 bbb 50% ccc"
    ))

    print(parse[int, float](
        t"aaa {None} bbb {None} ccc",
        "aaa 111 bbb 50 ccc"
    ))
    print(Parser[int, float](
        t"aaa {None} bbb {None} ccc",
    ).parse("aaa 111 bbb 50 ccc"))

    print(parse[*tuple[int, ...]](
        t"{None}+{None}*{None}-{None}",
        "123+333*567-999"
    ))
    print(parse[Unpack[tuple[int, ...]]](
        t"{None}+{None}*{None}-{None}",
        "123+333*567-999"
    ))

    try:
        parse(
            t"aaa {None} bbb {None} ccc",
            "aaa 111 bbb 50 ccc"
        )
    except ValueError as e:
        print(e)
    try:
        parse[int](
            t"aaa {None} bbb {None} ccc",
            "aaa 111 bbb 50 ccc"
        )
    except ValueError as e:
        print(e)
    try:
        print(parse[int, float](
            t"aaa {None} bbb {None} ccc",
            "abc"
        ))
    except ValueError as e:
        print(e)
    try:
        parse[int, float](
            t"aaa {None} bbb {1} ccc",
            "aaa 111 bbb 50 ccc"
        )
    except TypeError as e:
        print(e)
