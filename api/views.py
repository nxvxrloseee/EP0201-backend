from io import BytesIO
from datetime import date, timedelta
from django.http import HttpResponse
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action, permission_classes, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

# Импорт ReportLab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus.flowables import HRFlowable
    import os

    REPORTLAB_AVAILABLE = True

    # Регистрация шрифтов DejaVu для поддержки кириллицы
    try:
        fonts_dir = os.path.join(settings.BASE_DIR, 'static', 'fonts')
        if os.path.exists(fonts_dir):
            pdfmetrics.registerFont(TTFont('DejaVuSans', os.path.join(fonts_dir, 'DejaVuSans.ttf')))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf')))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Oblique', os.path.join(fonts_dir, 'DejaVuSans-Oblique.ttf')))
            FONT_NAME = 'DejaVuSans'
            FONT_NAME_BOLD = 'DejaVuSans-Bold'
        else:
            FONT_NAME = 'Helvetica'
            FONT_NAME_BOLD = 'Helvetica-Bold'
    except Exception as e:
        print(f"Ошибка загрузки шрифтов: {e}")
        FONT_NAME = 'Helvetica'
        FONT_NAME_BOLD = 'Helvetica-Bold'

except ImportError:
    REPORTLAB_AVAILABLE = False
    FONT_NAME = 'Helvetica'
    FONT_NAME_BOLD = 'Helvetica-Bold'

from .serializers import *
from .permissions import IsStaffOrReadOnly


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffOrReadOnly]


class MTokenObtainPairView(TokenObtainPairView):
    serializer_class = MTokenObtainPairSerializer


class TrainerListViewSet(BaseViewSet):
    queryset = Trainer.objects.all()
    serializer_class = TrainerSerializer


class HallViewSet(BaseViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer


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


def get_custom_styles():
    """Создание кастомных стилей для PDF"""
    styles = getSampleStyleSheet()

    # Стиль для главного заголовка
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontName=FONT_NAME_BOLD,
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10,
        alignment=TA_CENTER,
        leading=28
    ))

    # Стиль для подзаголовка
    styles.add(ParagraphStyle(
        name='CustomSubtitle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=TA_CENTER
    ))

    # Стиль для секций
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontName=FONT_NAME_BOLD,
        fontSize=14,
        textColor=colors.HexColor('#27ae60'),
        spaceBefore=15,
        spaceAfter=10,
        leading=16
    ))

    # Стиль для summary блока
    styles.add(ParagraphStyle(
        name='SummaryText',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        textColor=colors.HexColor('#2c3e50'),
        spaceBefore=5,
        spaceAfter=5,
        leading=14
    ))

    # Стиль для обычного текста
    styles.add(ParagraphStyle(
        name='CustomNormal',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=12
    ))

    return styles


def create_report_header(elements, title, subtitle, styles):
    """Создание заголовка отчета"""
    # Заголовок
    elements.append(Paragraph(title, styles['CustomTitle']))

    # Подзаголовок с датой
    elements.append(Paragraph(subtitle, styles['CustomSubtitle']))

    # Разделительная линия
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor('#27ae60'),
        spaceBefore=5,
        spaceAfter=15
    ))


def create_summary_box(elements, summary_items, styles):
    """Создание блока с итоговой информацией"""
    # Создаем таблицу для summary
    summary_data = []
    for item in summary_items:
        summary_data.append([
            Paragraph(f"<b>{item['label']}:</b>", styles['SummaryText']),
            Paragraph(str(item['value']), styles['SummaryText'])
        ])

    summary_table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ecf0f1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7'))
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.5 * cm))


def create_data_table(headers, data_rows, col_widths=None):
    """Создание таблицы с данными"""
    # Формируем данные таблицы
    table_data = [headers] + data_rows

    # Создаем таблицу
    if col_widths:
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
    else:
        table = Table(table_data, repeatRows=1)

    # Применяем стили
    table.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), FONT_NAME_BOLD),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

        # Содержимое
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('FONTNAME', (0, 1), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),

        # Чередующиеся строки
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),

        # Границы
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#34495e')),
    ]))

    return table


def create_pdf_document(title, subtitle, summary_items, headers, data_rows, col_widths=None):
    """
    Универсальная функция для создания PDF отчетов
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab не установлен")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title
    )

    elements = []
    styles = get_custom_styles()

    # Заголовок отчета
    create_report_header(elements, title, subtitle, styles)

    # Блок с итоговой информацией
    if summary_items:
        create_summary_box(elements, summary_items, styles)

    # Секция с данными
    elements.append(Paragraph("Детализация", styles['SectionHeader']))
    elements.append(Spacer(1, 0.3 * cm))

    # Таблица с данными
    table = create_data_table(headers, data_rows, col_widths)
    elements.append(table)

    # Футер
    elements.append(Spacer(1, 1 * cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['CustomNormal'],
        fontSize=8,
        textColor=colors.HexColor('#95a5a6'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        f"Отчёт сформирован автоматически • Система управления фитнес-клубом • {date.today().strftime('%d.%m.%Y')}",
        footer_style
    ))

    # Генерируем PDF
    doc.build(elements)
    buffer.seek(0)

    return buffer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_report(request):
    """Финансовый отчёт"""
    if not REPORTLAB_AVAILABLE:
        return Response(
            {'error': 'PDF библиотека не установлена. Установите: pip install reportlab'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        from .models import Payment

        payments = Payment.objects.select_related('client').order_by('-payment_date')
        total = sum(float(p.amount) for p in payments)

        # Summary данные
        summary_items = [
            {'label': 'Общая выручка', 'value': f"{total:,.2f} ₽"},
            {'label': 'Всего платежей', 'value': payments.count()}
        ]

        # Подготовка данных для таблицы
        headers = ['Дата', 'Клиент', 'Сумма', 'Тип оплаты']
        data_rows = []

        for p in payments:
            data_rows.append([
                p.payment_date.strftime('%d.%m.%Y %H:%M'),
                f"{p.client.surname} {p.client.name}",
                f"{float(p.amount):,.2f} ₽",
                p.payment_type
            ])

        # Ширина колонок
        col_widths = [4 * cm, 5 * cm, 3 * cm, 4 * cm]

        # Генерация PDF
        pdf_buffer = create_pdf_document(
            title="ФИНАНСОВЫЙ ОТЧЁТ",
            subtitle=f"Период: все время • Дата формирования: {date.today().strftime('%d.%m.%Y')}",
            summary_items=summary_items,
            headers=headers,
            data_rows=data_rows,
            col_widths=col_widths
        )

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="revenue_report.pdf"'
        return response

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_report(request):
    """Отчёт по посещаемости"""
    if not REPORTLAB_AVAILABLE:
        return Response(
            {'error': 'PDF библиотека не установлена. Установите: pip install reportlab'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        from .models import Attendance

        attendances = Attendance.objects.select_related(
            'client', 'training', 'training__trainer', 'training__training_type'
        ).filter(status='Посетил').order_by('-training__date_time')

        # Summary данные
        summary_items = [
            {'label': 'Всего посещений', 'value': attendances.count()},
            {'label': 'Период', 'value': 'Все время'}
        ]

        # Подготовка данных для таблицы
        headers = ['Дата', 'Клиент', 'Тренировка', 'Тренер']
        data_rows = []

        for a in attendances:
            data_rows.append([
                a.training.date_time.strftime('%d.%m.%Y %H:%M'),
                f"{a.client.surname} {a.client.name}",
                a.training.training_type.name,
                f"{a.training.trainer.surname} {a.training.trainer.name}"
            ])

        # Ширина колонок
        col_widths = [4 * cm, 4.5 * cm, 4 * cm, 4.5 * cm]

        # Генерация PDF
        pdf_buffer = create_pdf_document(
            title="ОТЧЁТ ПО ПОСЕЩАЕМОСТИ",
            subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')}",
            summary_items=summary_items,
            headers=headers,
            data_rows=data_rows,
            col_widths=col_widths
        )

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'
        return response

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trainer_performance_report(request):
    """Отчёт по эффективности тренеров"""
    if not REPORTLAB_AVAILABLE:
        return Response(
            {'error': 'PDF библиотека не установлена. Установите: pip install reportlab'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        from .models import Trainer
        from django.db.models import Count

        trainers = Trainer.objects.annotate(
            training_count=Count('training')
        ).order_by('-training_count')

        total_trainings = sum(t.training_count for t in trainers)

        # Summary данные
        summary_items = [
            {'label': 'Всего тренеров', 'value': trainers.count()},
            {'label': 'Всего тренировок', 'value': total_trainings}
        ]

        # Подготовка данных для таблицы
        headers = ['Тренер', 'Специализация', 'Кол-во тренировок']
        data_rows = []

        for t in trainers:
            data_rows.append([
                f"{t.surname} {t.name}",
                t.specialization,
                str(t.training_count)
            ])

        # Ширина колонок
        col_widths = [5 * cm, 7 * cm, 4 * cm]

        # Генерация PDF
        pdf_buffer = create_pdf_document(
            title="ЭФФЕКТИВНОСТЬ ТРЕНЕРОВ",
            subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')}",
            summary_items=summary_items,
            headers=headers,
            data_rows=data_rows,
            col_widths=col_widths
        )

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="trainer_performance.pdf"'
        return response

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiring_memberships_report(request):
    """Отчёт по истекающим абонементам"""
    if not REPORTLAB_AVAILABLE:
        return Response(
            {'error': 'PDF библиотека не установлена. Установите: pip install reportlab'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        from .models import Membership

        soon = date.today() + timedelta(days=7)
        expiring = Membership.objects.filter(
            end_date__lte=soon,
            status='Активен'
        ).select_related('client', 'type').order_by('end_date')

        # Summary данные
        summary_items = [
            {'label': 'Критических абонементов', 'value': expiring.count()},
            {'label': 'Период проверки', 'value': '7 дней'}
        ]

        # Подготовка данных для таблицы
        headers = ['Клиент', 'Тип абонемента', 'Дата окончания', 'Осталось дней']
        data_rows = []

        for m in expiring:
            days_left = (m.end_date - date.today()).days
            # Цвет предупреждения
            if days_left <= 0:
                days_text = f"ИСТЁК"
            elif days_left <= 3:
                days_text = f"{days_left} (срочно!)"
            else:
                days_text = str(days_left)

            data_rows.append([
                f"{m.client.surname} {m.client.name}",
                m.type.name,
                m.end_date.strftime('%d.%m.%Y'),
                days_text
            ])

        # Ширина колонок
        col_widths = [5 * cm, 5 * cm, 3 * cm, 3 * cm]

        # Генерация PDF
        pdf_buffer = create_pdf_document(
            title="ИСТЕКАЮЩИЕ АБОНЕМЕНТЫ",
            subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')} • Проверка на {soon.strftime('%d.%m.%Y')}",
            summary_items=summary_items,
            headers=headers,
            data_rows=data_rows,
            col_widths=col_widths
        )

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="expiring_memberships.pdf"'
        return response

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )