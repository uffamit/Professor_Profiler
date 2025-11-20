class Runner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def run_async(self, **kwargs):
        yield
