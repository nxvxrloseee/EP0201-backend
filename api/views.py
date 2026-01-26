import os
from django.conf import settings
from django.db.models import Sum, Count
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import *
from .serializers import *
from .permissions import IsAdminOrManager

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAdminOrManager] # Только админ и менеджер управляют клиентами

class TrainingViewSet(viewsets.ModelViewSet):
    queryset = Training.objects.all()
    serializer_class = TrainingSerializer

    # Функция записи клиента на тренировку
    @action(detail=True, methods=['post'])
    def register_client(self, request, pk=None):
        training = self.get_object()
        client_id = request.data.get('client_id')

        # Проверка лимита мест
        current_count = Attendance.objects.filter(training=training).count()
        if current_count >= training.max_clients:
            return Response({'error': 'Мест нет'}, status=status.HTTP_400_BAD_REQUEST)

        Attendance.objects.create(client_id=client_id, training=training, status='Записан')
        return Response({'status': 'Клиент записан'})


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    # Отчет по доходам за период (для Руководителя)
    @action(detail=False, methods=['get'])
    def revenue_report(self, request):
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')
        total = Payment.objects.filter(payment_date__range=[start_date, end_date]).aggregate(models.Sum('amount'))
        return Response({'total_revenue': total['amount__sum'] or 0})




FONT_PATH = os.path.join(settings.BASE_DIR, 'static/fonts/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf')
pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_PATH))

class ReportViewSet(viewsets.ViewSet):
    queryset = Payment.objects.none()

    def _render_pdf_table(self, title, headers, data, total_label=None, total_val=None):
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Стиль для заголовка (кириллица)
        title_style = ParagraphStyle(
            'TitleStyle', parent=styles['Heading1'], fontName='DejaVu', alignment=1
        )
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 20))

        # Подготовка данных для таблицы
        table_data = [headers] + data
        if total_label:
            table_data.append(['', total_label, total_val])

        # Создание таблицы
        t = Table(table_data, colWidths=[150, 150, 100])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'DejaVu'), # Применяем русский шрифт ко всей таблице
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ]))

        elements.append(t)
        doc.build(elements)
        return response

    @action(detail=False, methods=['get'])
    def finance(self, request):
        payments = Payment.objects.all()
        total = payments.aggregate(total=Sum('amount'))['total'] or 0

        headers = ['Дата', 'Клиент', 'Сумма (руб.)']
        data = [
            [p.payment_date.strftime('%d.%m.%Y'), p.client.surname, str(p.amount)]
            for p in payments
        ]

        return self._render_pdf_table(
            "ФИНАНСОВЫЙ ОТЧЕТ — ФИТНЕС-ЛАЙФ",
            headers, data, "ИТОГО:", str(total)
        )

    @action(detail=False, methods=['get'])
    def attendance(self, request):
        stats = Attendance.objects.filter(is_present=True).values('training__hall__name').annotate(count=Count('id'))
        headers = ['Зал', 'Количество посещений', 'Статус']
        data = [[s['training__hall__name'], str(s['count']), 'Норма'] for s in stats]
        return self._render_pdf_table("ОТЧЕТ ПОСЕЩАЕМОСТИ", headers, data)