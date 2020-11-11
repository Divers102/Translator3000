# -*- coding: utf-8 -*-
"""
@author: Vladya
"""

import time
import re
import threading
from os import path
from . import (
    LOGGER,
    DEBUG_FOLDER,
    utils,
    _url_getter,
    _url_opener
)


class TokenGenerator(object):

    __author__ = "Vladya"

    _tkk_re = re.compile(r"(?<=tkk:\')\d+\.\d+(?=\')")
    LOGGER = LOGGER.getChild("TokenGenerator")

    MAX_ATTEMPT = 10

    def __init__(self):

        self.__tkk = None
        self.__lock = threading.Lock()

    def __call__(self, text):
        return self._generate_token_for_text(text)

    @property
    def tkk(self):
        return self._get_tkk(force_update=False)

    def _get_tkk(self, force_update=False):

        self.LOGGER.debug("'TKK' requested.")
        with self.__lock:
            if force_update or (not self.__tkk):
                if not self.__tkk:
                    self.LOGGER.debug("'TKK' was not found. Start updating.")
                elif force_update:
                    self.LOGGER.debug("Requested 'TKK' force updating.")
                self.__update_tkk()

            token_hour, _ = map(int, self.__tkk.split('.'))
            current_hour = int(((time.time() / 60.) / 60.))
            if token_hour != current_hour:
                self.LOGGER.debug("'TKK' has expired. Start updating.")
                self.__update_tkk()

            self.LOGGER.debug("Returning 'TKK'.")
            return self.__tkk

    def __update_tkk(self):

        _counter = 0
        while True:
            _counter += 1
            self.LOGGER.debug("Updating 'TKK'. Attempt %d.", _counter)
            result = _url_opener.get(_url_getter.base)
            new_tkk = self._tkk_re.search(result.content)
            if not new_tkk:
                utils._save_data_to_file(
                    result.content,
                    path.join(DEBUG_FOLDER, u"page_without_token.html")
                )
                if _counter >= self.MAX_ATTEMPT:
                    raise Exception("Not find 'TKK'.")
                self.LOGGER.error("Not find 'TKK'. Try again...")
                continue
            break
        new_tkk = new_tkk.group()
        if isinstance(new_tkk, unicode):
            new_tkk = new_tkk.encode("utf_8")
        self.__tkk = new_tkk
        self.LOGGER.debug("'TKK' has been successfully updated.")

    def _generate_token_for_text(self, text):

        """
        Create a unique code that is normally generated by the browser
        when working in the web version.

        The code below do not have any specific logic.
        Impersonating the browser by simulating the execution
        of obfuscated Google code.

        Deobfuscation is based on the logic implemented by a "ssut"
        in the project "py-googletrans", adapted to specific needs.

        LINK: https://github.com/ssut/py-googletrans/blob/
        4f7c0798fe6b235164b47d4542536f562795a419/googletrans/gtoken.py#L137
        """

        self.LOGGER.debug("Start generating token for the text.")

        text_bytes = tuple(map(ord, text))
        tkk_parts = tuple(map(int, self.tkk.split('.')))

        code_array = []
        _size = len(text_bytes)
        skip_byte = False

        for counter, current_byte in enumerate(text_bytes):
            if skip_byte:
                skip_byte = False
                continue
            if (counter + 1) < _size:
                next_byte = text_bytes[(counter + 1)]
            else:
                next_byte = None
            if current_byte < 0x80:
                code_array.append(current_byte)
            else:
                if current_byte < 0x800:
                    code_array.append(((current_byte >> 0b110) | 0b11000000))
                else:
                    if (
                        ((current_byte & 0xfc00) == 0xd800) and
                        (next_byte is not None) and
                        ((next_byte & 0xfc00) == 0xdc00)
                    ):
                        current_byte = (
                            0b10000000000000000 + (
                                ((current_byte & 0b1111111111) << 0b1010)
                            ) + (
                                (next_byte & 0b1111111111)
                            )
                        )
                        code_array.append(
                            ((current_byte >> 0b10010) | 0b11110000)
                        )
                        code_array.append(
                            (((current_byte >> 0b1100) & 0b111111) | 0x80)
                        )
                        skip_byte = True
                    else:
                        code_array.append(
                            ((current_byte >> 0b1100) | 0b11100000)
                        )
                    code_array.append(
                        (((current_byte >> 0b110) & 0b111111) | 0b10000000)
                    )
                code_array.append(
                    ((current_byte & 0b111111) | 0b10000000)
                )

        value = tkk_parts[0]
        for counter, modifier in enumerate(code_array):
            value += modifier
            value = self._strange_modifier(value, "+-a^+6")
        value = self._strange_modifier(value, "+-3^+b+-f")
        value ^= tkk_parts[1]

        if value < 0:
            value = ((value & 0x7fffffff) + 0x80000000)

        value %= 1000000
        self.LOGGER.debug("Token has been generated.")
        return "{0}.{1}".format(value, (value ^ tkk_parts[0]))

    @classmethod
    def _strange_modifier(cls, value, text_commands):

        for a, b, c in map(
            lambda x: text_commands[(x * 3):((x * 3) + 3)],
            xrange((len(text_commands) // 3))
        ):

            modifier = int(c, 16)

            if b == '+':
                modifier = cls.rshift_with_pad(value, modifier)
            else:
                modifier = value << modifier

            if a == '+':
                value = ((value + modifier) & 0xffffffff)
            else:
                value ^= modifier

        return value

    @staticmethod
    def rshift_with_pad(a, b):

        """
        Realization of JS '>>>'.
        """

        if not isinstance(a, (int, long)):
            raise TypeError("Only 'int' type supported bit operations.")

        if a < 0:

            a = abs(a)
            if a > 0x7fffffff:
                raise NotImplementedError(
                    "Negative numbers longer than 31 bits are not supported."
                )

            a |= 0x80000000  # 32 bits of negative number.
            a ^= 0x7fffffff  # Invert the last 31 bits.
            a += 1

        return (a >> b)
