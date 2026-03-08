import os
import json
import inspect
import logging

# A global cache of logger instances, by name
loggers = {}


class LoggerNames:
    API = 'api'
    CLOUD_FN = 'cloud_functions'
    LOCAL = 'local_dev'


class Logger:
    """
    A Logger class that writes logs differently depending on environment:

      - Locally (K_SERVICE not set): Uses a StreamHandler with a human-readable string format
      - In Cloud Functions (K_SERVICE is set): Emits JSON logs (one line of JSON per log event),
        which GCF automatically parses as structured logs.
    """

    def __init__(
        self,
        log_name: str,
        workout_id: str = None,
        unit_id: str = None,
        class_name: str = None,
    ) -> None:
        global loggers

        # If we already created a logger for this log_name, reuse it.
        if log_name in loggers:
            self.logger = loggers[log_name]
        else:
            # Create or get a logger
            self.logger = logging.getLogger(log_name)
            self.logger.setLevel(logging.DEBUG)

            # If no handlers, add one
            if not self.logger.hasHandlers():
                stream_handler = logging.StreamHandler()
                stream_handler.setLevel(logging.DEBUG)

                # If we're NOT in Cloud Functions, show a human-friendly format
                if not os.getenv('K_SERVICE'):
                    formatter = logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(json_fields)s'
                    )
                    stream_handler.setFormatter(formatter)
                # If we *are* in Cloud Functions, we won't rely on the formatter
                # (we'll pass JSON strings to logger.* calls). However, we still
                # need a handler so logs go to stdout.
                self.logger.addHandler(stream_handler)

            loggers[log_name] = self.logger

        # These fields get included in every log record
        self.workout_id = workout_id
        self.unit_id = unit_id
        self.class_name = class_name

        # We'll store whether we want structured logs
        self.structured_logs = bool(os.getenv('K_SERVICE'))

    @property
    def workout_id(self) -> str:
        return self._workout_id

    @workout_id.setter
    def workout_id(self, new_value: str) -> None:
        self._workout_id = new_value

    @property
    def unit_id(self) -> str:
        return self._unit_id

    @unit_id.setter
    def unit_id(self, new_value: str) -> None:
        self._unit_id = new_value

    @property
    def class_name(self) -> str:
        return self._class_name

    @class_name.setter
    def class_name(self, value: str) -> None:
        self._class_name = value

    def _common_fields(self, **kwargs) -> dict:
        """
        Gathers default fields like caller, workout_id, etc.
        """
        caller = inspect.currentframe().f_back.f_back.f_back.f_back.f_code.co_name
        base_fields = {
            'caller': caller,
        }
        if self.unit_id:
            base_fields['unit_id'] = self.unit_id
        if self.workout_id:
            base_fields['workout_id'] = self.workout_id
        if self.class_name:
            base_fields['class_name'] = self.class_name

        # Merge user kwargs
        base_fields.update(kwargs)
        return base_fields

    def _log_json(self, level: str, message: str, **kwargs) -> None:
        """
        Emit structured JSON logs for GCF.
        """
        fields = self._common_fields(**kwargs)
        log_obj = {
            'severity': level.upper(),
            'message': message,
            **fields
        }
        # We call the standard logger with a single JSON string
        # The "extra" isn't used by default in JSON logs, so we embed everything in the message.
        getattr(self.logger, level.lower())(json.dumps(log_obj))

    def _log_text(self, level: str, message: str, **kwargs) -> None:
        """
        Emit a normal text log with extra fields as 'json_fields'.
        """
        fields = self._common_fields(**kwargs)
        self.logger.log(
            getattr(logging, level.upper()),
            message,
            extra={'json_fields': fields}
        )

    def _log(self, level: str, message: str, **kwargs) -> None:
        """
        Decide whether to emit JSON logs (GCF) or text logs (local).
        """
        if self.structured_logs:
            # Cloud Functions environment → JSON logs
            self._log_json(level, message, **kwargs)
        else:
            # Local environment → text logs
            self._log_text(level, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log('ERROR', message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log('WARNING', message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._log('INFO', message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        self._log('DEBUG', message, **kwargs)
