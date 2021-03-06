from django.shortcuts import render
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.core.cache import cache

# Django Restful Framework
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListCreateAPIView
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny,
    IsAuthenticatedOrReadOnly,
)
from django_redis import get_redis_connection

from .serializers import (
    ActivitySerializer,
    ActivityInstanceSerializer,
    OrderSerializer,
    UidSerializer,
)
from .constants import SECKILL_CONSTANT

# Moddels
from .models import Activity, Product, Order


class ActivityList(GenericAPIView):
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
    serializer_class = ActivitySerializer
    queryset = Activity.objects.all()

    def get(self, request, format=None):
        """
        Getting activity list
        """
        activities = self.filter_queryset(self.get_queryset()).order_by("id")
        serializer = ActivitySerializer(activities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ActivityInstance(GenericAPIView):
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
    serializer_class = UidSerializer
    queryset = ""

    def get(self, request, pk, format=None):
        """
        Get activity instance by pk, with product detail information
        """
        try:
            activity = Activity.objects.get(pk=pk)
        except Activity.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ActivityInstanceSerializer(activity)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk, format=None):
        """
        Place an order with current activity
        activity state: PREPARING, RUNNING, OVER
        """
        uuid = request.data.get("uuid", False)
        if not uuid:
            context = {"msg": SECKILL_CONSTANT["REQUIRED_UUID"]}
            return Response(context, status=status.HTTP_400_BAD_REQUEST)
        # activity = cache.get(f"activity-{pk}")
        # redis_con = get_redis_connection("default")
        # if not activity:
        try:
            activity = Activity.objects.get(pk=pk)
            # cache.set(f"activity-{pk}", activity)
            # redis_con.hset(f"activity-{pk}", "total", activity.product.inventory)
            # redis_con.hset(f"activity-{pk}", "access", 0)
        except Activity.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if activity.get_status() == "RUNNING":
            if activity.product.inventory <= 0:
                # if int(redis_con.hget(f"activity-{pk}", "total")) <= int(
                #    redis_con.hget(f"activity-{pk}", "access")
                # ):
                context = {"msg": SECKILL_CONSTANT["EMPTY_INVENTPRY"]}
                return Response(context, status=status.HTTP_200_OK)
            # redis_con.hincrby(f"activity-{pk}", "access", 1)

            # return Response("ok", status=status.HTTP_201_CREATED)

            with transaction.atomic():
                try:
                    order = Order.objects.create(uuid=uuid, activity=activity)
                    product = Product.objects.select_for_update().get(
                        pk=activity.product.id
                    )
                    product.inventory -= 1
                    product.save()
                except ValidationError:
                    context = {"msg": SECKILL_CONSTANT["DUPLICATE_ORDER"]}
                    return Response(context, status=status.HTTP_200_OK)
                order = Order.objects.get(uuid=uuid, activity=activity)
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif activity.get_status() == "PREPARING":
            context = {"msg": SECKILL_CONSTANT["ACTIVITY_PREPARING"]}
            return Response(context, status=status.HTTP_200_OK)
        else:
            context = {"msg": SECKILL_CONSTANT["ACTIVITY_OVER"]}
            return Response(context, status=status.HTTP_200_OK)


class OrderList(GenericAPIView):
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)
    serializer_class = OrderSerializer
    queryset = Order.objects.all()

    def get(self, request, format=None):
        """
        Getting order list
        """
        uuid = request.GET.get("uuid", False)
        if not uuid:
            context = {"msg": SECKILL_CONSTANT["REQUIRED_UUID"]}
            return Response(context, status=status.HTTP_400_BAD_REQUEST)
        orders = self.get_queryset().filter(uuid=uuid)
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
