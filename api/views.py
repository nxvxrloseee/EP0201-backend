import os
from datetime import timedelta
from email import header
from django.conf import settings
from django.db.models import Sum, Count
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import *
from .permissions import IsStaffOrReadOnly

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffOrReadOnly]


class TrainerListViewSet(BaseViewSet):
    queryset = Trainer.objects.all()
    serializer_class = TrainerSerializer


class ClientViewSet(BaseViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


class MembershipViewSet(BaseViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer


class TrainingViewSet(BaseViewSet):
    queryset = Training.objects.all()
    serializer_class = TrainingSerializer

    @action(detail=True, methods=['post'])
    def register_client(self, request, pk=None):
        """Запись клиента на тренировку с проверкой вместимости (ТЗ 4.1)"""
        training = self.get_object()
        client_id = request.data.get('client_id')

        if training.attendance_set.count() >= training.max_clients:
            return Response({'error': 'Мест больше нет'}, status=status.HTTP_400_BAD_REQUEST)

        Attendance.objects.create(
            client_id=client_id,
            training=training,
            status='Записан'
        )
        return Response({'status': 'Клиент записан'}, status=status.HTTP_201_CREATED)


class PaymentViewSet(BaseViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet для генерации аналитических отчетов в формате PDF.
    Соответствует требованиям ТЗ и Приложения А.
    """
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def _get_pdf_response(self, filename):
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        return response

    def _setup_fonts(self):
        # Путь к шрифтам на основе структуры вашего проекта
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'dejavu-fonts-ttf-2.37', 'ttf', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

    def _render_pdf_table(self, title, headers, data):
        self._setup_fonts()
        response = HttpResponse(content_type='application/pdf')
        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Настройка стиля заголовка
        title_style = styles["Heading1"]
        title_style.fontName = 'DejaVuSans'
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 12))

        # Создание таблицы
        table_data = [headers] + data
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(t)
        doc.build(elements)
        return response

    @action(detail=False, methods=['get'])
    def revenue(self, request):
        """Финансовый отчёт (Рисунок 1 из Приложения А)"""
        payments = Payment.objects.all().order_by('-payment_date')
        total = payments.aggregate(Sum('amount'))['amount__sum'] or 0

        headers = ['Дата', 'Клиент', 'Тип оплаты', 'Сумма']
        data = [
            [
                p.payment_date.strftime('%d.%m.%Y'),
                f"{p.client.surname} {p.client.name[0]}.",
                p.payment_type,
                f"{p.amount} руб."
            ] for p in payments
        ]
        data.append(['', '', 'ИТОГО:', f"{total} руб."])
        return self._render_pdf_table("ФИНАНСОВЫЙ ОТЧЕТ", headers, data)

    @action(detail=False, methods=['get'])
    def attendance(self, request):
        """Отчёт посещаемости (Рисунок 2 из Приложения А)"""
        # Фильтруем только тех, кто реально пришел (is_present=True)
        attendances = Attendance.objects.filter(is_present=True).select_related('client', 'training')

        headers = ['Дата', 'Клиент', 'Тренировка', 'Статус']
        data = [
            [
                a.training.date_time.strftime('%d.%m.%Y'),
                f"{a.client.surname} {a.client.name}",
                a.training.training_type.name,
                "Посетил"
            ] for a in attendances
        ]
        return self._render_pdf_table("ОТЧЕТ ПОСЕЩАЕМОСТИ", headers, data)

    @action(detail=False, methods=['get'])
    def trainer_performance(self, request):
        """Отчёт о работе тренеров (Рисунок 3 из Приложения А)"""
        stats = Training.objects.values('trainer__surname', 'trainer__name').annotate(
            total_trainings=Count('id', distinct=True),
            total_clients=Count('attendance')
        ).order_by('-total_trainings')

        headers = ['Тренер', 'Проведено занятий', 'Всего клиентов (записей)']
        data = [
            [
                f"{s['trainer__surname']} {s['trainer__name']}",
                str(s['total_trainings']),
                str(s['total_clients'])
            ] for s in stats
        ]
        return self._render_pdf_table("ЭФФЕКТИВНОСТЬ ТРЕНЕРОВ", headers, data)

    @action(detail=False, methods=['get'])
    def expiring_memberships(self, request):
        """Список клиентов с истекающим абонементом (Рисунок 4 из Приложения А)"""
        today = date.today()
        threshold = today + timedelta(days=7)  # Берем интервал в неделю

        memberships = Membership.objects.filter(
            end_date__range=[today, threshold],
            status='Активен'
        ).select_related('client', 'type')

        headers = ['Клиент', 'Телефон', 'Тип абонемента', 'Дата окончания']
        data = [
            [
                f"{m.client.surname} {m.client.name}",
                m.client.phone,
                m.type.name,
                m.end_date.strftime('%d.%m.%Y')
            ] for m in memberships
        ]
        return self._render_pdf_table("ИСТЕКАЮЩИЕ АБОНЕМЕНТЫ (ближайшие 7 дней)", header, data)