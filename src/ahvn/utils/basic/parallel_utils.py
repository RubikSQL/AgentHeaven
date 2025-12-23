__all__ = [
    "Parallelized",
]

from .log_utils import get_logger
from .progress_utils import Progress, TqdmProgress

logger = get_logger(__name__)

from typing import Generator, Callable, Iterable, Any, Tuple, Dict, List, Optional, Type
from concurrent.futures import ThreadPoolExecutor, as_completed, Future


class Parallelized:
    def __init__(
        self,
        func: Callable,
        args: Iterable[Dict[str, Any]] = None,
        num_threads: Optional[int] = None,
        desc: str = None,
        progress: Optional[Type[Progress]] = None,
    ):
        """\
        Initialize a parallelized task executor with progress tracking.

        Args:
            func (Callable): The function to execute in parallel (should always accept kwargs only).
            args (Iterable[Dict[str, Any]]): Iterable of argument dictionaries to pass as kwargs.
            num_threads (Optional[int]): Number of worker threads. Defaults to None, which uses unlimited threads as per ThreadPoolExecutor.
            desc (Optional[str]): Description for the progress bar. Defaults to None.
            progress (Optional[Type[Progress]]): Progress class to use. Defaults to TqdmProgress.
        """
        self.func = func
        self.args = list(args)
        self.total = len(args)
        self.num_threads = num_threads
        self.desc = desc
        self._progress_cls = progress or TqdmProgress

        self._tasks: List[Future] = list()
        self._progress: Optional[Progress] = None
        self._executor = None
        self._interrupted = False

    def __enter__(self):
        """\
        Enter the runtime context related to this object.

        Returns:
            self: The Parallelized instance itself, which can be iterated over to yield results.

        Usage:
            with Parallelized(func, args) as ptasks:
                ptasks.progress.set_description("Processing tasks")
                for args, result, error in ptasks:
                    ...
        """
        self._executor = ThreadPoolExecutor(max_workers=self.num_threads)
        self._progress = self._progress_cls(total=self.total, desc=self.desc)
        for kwargs in self.args:
            if not isinstance(kwargs, dict):
                raise TypeError(f"All arguments must be dictionaries, got {type(kwargs)}: {kwargs}")
            self._tasks.append(self._executor.submit(self._execute_task, kwargs))
        return self

    def _execute_task(self, kwargs: Dict) -> Tuple[Dict[str, Any], Any, Optional[Exception]]:
        if self._interrupted:
            return (kwargs, None, KeyboardInterrupt("Task cancelled due to interruption or exit."))
        try:
            result = self.func(**kwargs)
            return (kwargs, result, None)
        except Exception as e:
            logger.error(f"Task failed: {self.func.__name__}. kwargs: {repr(kwargs)}.")
            return (kwargs, None, e)

    def _handle_interrupt(self):
        self._interrupted = True
        logger.warning("\nKeyboardInterrupt/SystemExit received, cancelling pending tasks...")
        self._progress.write("\nKeyboardInterrupt/SystemExit received, cancelling pending tasks...")
        cancelled = 0
        for future in self._tasks:
            if not future.done():
                future.cancel()
                cancelled += 1
        logger.info(f"Cancelled {cancelled} pending tasks.")
        self._progress.write(f"Cancelled {cancelled} pending tasks.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type in [KeyboardInterrupt, SystemExit]:
            self._handle_interrupt()
        self._executor.shutdown(wait=not self._interrupted)
        self._progress.close()
        return exc_type in [KeyboardInterrupt, SystemExit]

    def __iter__(self) -> Generator[Tuple[Dict[str, Any], Any, Optional[Exception]], None, None]:
        try:
            for future in as_completed(self._tasks):
                if self._interrupted:
                    break
                kwargs, result, error = future.result()
                self._progress.update(1)
                yield (kwargs, result, error)
        except KeyboardInterrupt as e:
            self._handle_interrupt()
            raise e
        except SystemExit as e:
            self._handle_interrupt()
            raise e

    @property
    def progress(self) -> Progress:
        """Access the progress bar."""
        return self._progress

    @property
    def pbar(self) -> Progress:
        """Alias for progress (backward compatibility)."""
        return self._progress
