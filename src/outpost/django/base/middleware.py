class RemoteAddrMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            request.META['REMOTE_ADDR'] = next(
                iter(
                    request.META['HTTP_X_FORWARDED_FOR'].split(',')
                )
            ).strip()
        response = self.get_response(request)
        return response
