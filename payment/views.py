import datetime
import decimal
import logging
import random

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .alipay import Alipay
from .models import *
from .wechat import Wechat

logger = logging.getLogger(__name__)


class PayView(APIView):
    """
    获取支付数据用于APP调起SDK支付
    参数:
        platform: wechat,alipay
        amount: 0.01
    """
    permission_classes = ((IsAuthenticated,))
    def _make_trade_no(self):
        return datetime.datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randrange(1000,9999))

    def post(self, request, format=None):
        try:
            amount = decimal.Decimal(request.data['amount'])
            action = request.data.get('action', 'recharge')
            description = request.data.get('description', '')
            extra = request.data.get('extra', '')
            platform = request.data.get('platform', 'wechat')
        except:
            return Response(
                    {'detail': '参数不正确'},
                    status=status.HTTP_400_BAD_REQUEST)

        out_trade_no = self._make_trade_no()
        log = Log.objects.create(
                method = platform,
                user = request.user,
                action = action,
                number = out_trade_no,
                amount = amount,
                description = description,
                extra = extra,
                )

        if platform == 'wechat':
            obj = Wechat()
        else:
            obj = Alipay()

        data = obj.get_pay_data(log, request.META['REMOTE_ADDR'])

        return Response(data)

@csrf_exempt
def notify_view(request, method):
    """
    接收支付结果异步通知
    """

    if method == 'wechat':
        obj = Wechat()
        success, data = obj.parse_result(request.body)
    else:
        obj = Alipay()
        success, data = obj.parse_result(request.POST)

    if not success:
        return HttpResponse(obj.return_failure())

    if not obj.check_result(data):
        return HttpResponse(obj.return_failure())

    try:
        log = Log.objects.get(number=data['out_trade_no'],
                method=method,
                is_success=False)
        log.is_success = True
        log.extra = str(data)
        log.save()

        return HttpResponse(obj.return_success())
    except Exception as e:
        logger.debug(e)

        return HttpResponse(obj.return_failure())
