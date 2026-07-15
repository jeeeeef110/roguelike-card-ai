"""pytest 最小替身:無網路環境用。支援本專案測試用到的 raises 與 mark.parametrize。
真正的 pytest 可用時,刪除本檔即可(本檔不進 repo,只存在於沙盒)。"""
import contextlib


@contextlib.contextmanager
def raises(exc_type):
    class _Info:
        value = None

    info = _Info()
    try:
        yield info
    except exc_type as e:
        info.value = e
    else:
        raise AssertionError(f"未拋出預期的 {exc_type.__name__}")


class _Mark:
    @staticmethod
    def parametrize(argnames, argvalues):
        def deco(fn):
            fn._parametrize = (argnames, list(argvalues))
            return fn
        return deco


mark = _Mark()
