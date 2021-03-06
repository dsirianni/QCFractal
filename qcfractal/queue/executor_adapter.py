"""
Queue adapter for Dask
"""

import time
import traceback
from typing import Any, Dict, Hashable, List, Tuple

from .base_adapter import BaseAdapter


def _get_future(future):
    try:
        return future.result()
    except Exception as e:
        msg = traceback.format_exc()
        ret = {"success": False, "error_message": msg}
        return ret


class ExecutorAdapter(BaseAdapter):
    """A Queue Adapter for Python Executors
    """

    def __repr__(self):

        return "<ExecutorAdapter client=<{} max_workers={}>>".format(self.client.__class__.__name__,
                                                                     self.client._max_workers)

    def _submit_task(self, task_spec: Dict[str, Any]) -> Tuple[Hashable, Any]:
        func = self.get_function(task_spec["spec"]["function"])
        task = self.client.submit(func, *task_spec["spec"]["args"], **task_spec["spec"]["kwargs"])
        return task_spec["id"], task

    def acquire_complete(self) -> List[Dict[str, Any]]:
        ret = {}
        del_keys = []
        for key, future in self.queue.items():
            if future.done():
                ret[key] = _get_future(future)
                del_keys.append(key)

        for key in del_keys:
            del self.queue[key]

        return ret

    def await_results(self) -> bool:
        for future in self.queue.values():
            while future.done() is False:
                time.sleep(0.1)

        return True

    def close(self) -> bool:
        for future in self.queue.values():
            future.cancel()

        self.client.shutdown()
        return True


class DaskAdapter(ExecutorAdapter):
    """A Queue Adapter for Dask
    """

    def __repr__(self):

        return "<DaskAdapter client={}>".format(self.client)

    def _submit_task(self, task_spec: Dict[str, Any]) -> Tuple[Hashable, Any]:
        func = self.get_function(task_spec["spec"]["function"])

        # Watch out out for thread unsafe tasks and our own constraints
        task = self.client.submit(func, *task_spec["spec"]["args"], **task_spec["spec"]["kwargs"], resources={"process": 1})
        return task_spec["id"], task

    def await_results(self) -> bool:
        from dask.distributed import wait
        wait(list(self.queue.values()))
        return True

    def close(self) -> bool:

        self.client.close()
        return True
