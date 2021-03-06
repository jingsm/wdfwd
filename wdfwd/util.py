import os
import logging
import tempfile
import time
import re
from subprocess import check_call as _check_call, CalledProcessError

import win32file

fsender = None

def cap_call(cmd, retry=0, _raise=True, _test=False):
    logging.info('cap_call cmd: {}, retry: {}'.format(cmd, _raise))
    if retry > 0:
        for i in range(retry + 1):
            _raise = False if i < retry else True
            if i > 0:
                logging.debug("{} retry".format(i))
            if _cap_call(cmd, retry, _raise, _test):
                logging.debug("success")
                return
            # sleep for a while, then retry
            logging.debug("wait for a while")
            time.sleep(10)
    else:
        _cap_call(cmd, retry, _raise, _test)


def _cap_call(cmd, retry, _raise, _test=False):
    out = tempfile.TemporaryFile()
    err = tempfile.TemporaryFile()
    res = True
    try:
        logging.info('_cap_call: %s', str(cmd))
        _check_call(cmd, shell=True, stdout=out, stderr=err)
    except CalledProcessError, e:
        logging.error(str(e))
        res = False
        if _raise:
            raise
    finally:
        out.flush()
        err.flush()
        out.seek(0)
        err.seek(0)
        _out = out.read()
        _err = err.read()
        if len(_out) > 0:
            logging.debug(_out)
            if _test:
                print(_out)
        if len(_err) > 0:
            logging.error(_err)
            if _test:
                print(_err)
        if not _raise or res:
            return res


def escape_data_path(path):
    if 'library.zip' in path:
        return path.replace('\\library.zip\\wdfwd', '\\files')
    return path


def log_head(msg):
    logging.critical("==================== %s  ====================" % msg)


def safe_fname(fname):
    """
        Returns safe fname by eliminating chances of dir traversing
    """
    return fname.replace('../', '')


class ChangeDir(object):

    def __init__(self, *dirs):
        self.cwd = os.getcwd()
        self.path = os.path.join(*dirs)

    def __enter__(self):
        logging.info('change dir to %s', self.path)
        os.chdir(self.path)

    def __exit__(self, _type, value, tb):
        os.chdir(self.cwd)


def get_fileid(fh):
    info = win32file.GetFileInformationByHandle(fh)
    return sum(info[8:])


class OpenNoLock(object):

    def __init__(self, path):
        self.path = path
        self.handle = None

    def __enter__(self):
        return self.open()

    def open(self):
        self.handle = win32file.CreateFile(self.path, win32file.GENERIC_READ,
                                           win32file.FILE_SHARE_DELETE |
                                           win32file.FILE_SHARE_READ |
                                           win32file.FILE_SHARE_WRITE, None,
                                           win32file.OPEN_EXISTING,
                                           win32file.FILE_ATTRIBUTE_NORMAL,
                                           None)
        return self.handle

    def __exit__(self, _type, value, tb):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        if self.handle:
            win32file.CloseHandle(self.handle)
            self.handle = None
            self.fid = None


def get_dump_fname(_tbname, _date=None):
    tbname = _tbname.split('.')[-1]
    if _date is None:
        return "%s.csv" % tbname
    else:
        date = normalize_date_str(_date)
        return "{}_{}.csv".format(tbname, date)


def normalize_date_str(date):
    return date.replace('-', '')


def remove_file(fpath):
    try:
        if os.path.isfile(fpath):
            os.unlink(fpath)
    except OSError:
        logging.error("Failed: _remove_file " + fpath)


def ensure_endsep(path):
    return path if path.endswith('/') else path + '/'


def init_global_fsender(tag, host, port):
    from fluent.sender import FluentSender

    global fsender
    if fsender is None:
        fsender = FluentSender(tag, host, port)
        linfo("init_global_fsender")

def _log(level, msg):
    if logging.getLogger().getEffectiveLevel() > getattr(logging,
                                                         level.upper()):
        return

    lfun = getattr(logging, level)
    lfun(msg)
    if fsender:
        ts = int(time.time())
        try:
            fsender.emit_with_time(level, ts, {"message": msg})
        except Exception, e:
            logging.error("_log error - fsender.emit_with_time "
                          "'{}'".format(e))


def ldebug(msg):
    _log('debug', msg)


def lerror(msg):
    _log('error', msg)


def linfo(msg):
    _log('info', msg)


def lwarning(msg):
    _log('warning', msg)


def lcritical(msg):
    _log('critical', msg)


def lheader(msg):
    lcritical("============================== {} "
              "==============================".format(msg))

def escape_path(path):
    return path.replace("\\", "__").replace(":", "__")


class InvalidLogFormat(Exception):
    pass


class InvalidOrderPtrn(Exception):
    pass


def validate_format(ldebug, lerror, fmt):
    ldebug("validate_format {}".format(fmt))
    if not fmt:
        return

    if '(?P<dt_>' not in fmt:
        lerror("validate_format - not found 'dt_' part")
        raise InvalidLogFormat()

    # if ('(?P<_json_>' not in fmt) and ('(?P<_text_>' not in fmt):
        # lerror("validate_format - not found <_json_/_text_> part")
        # raise InvalidLogFormat()

    try:
        return re.compile(fmt)
    except Exception, e:
        lerror("validate_format '{}' - invalid format '{}'".format(e, fmt))
        raise InvalidLogFormat()


def validate_order_ptrn(ldebug, lerror, ptrn):
    ldebug("validate_order_ptrn - '{}'".format(ptrn))
    if not ptrn:
        return

    try:
        return re.compile(ptrn)
    except Exception, e:
        lerror("validate_order_ptrn - '{}'".format(e))
        raise InvalidOrderPtrn()
