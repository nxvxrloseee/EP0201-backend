from io import BytesIO
from datetime import timedelta
from django.http import FileResponse, JsonResponse
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

from backend.settings import FONTS_DIR


def jwt_authenticate(request):
    jwt_auth = JWTAuthentication()
    user_auth_tuple = jwt_auth.authenticate(request)

    if user_auth_tuple is None:
        raise AuthenticationFailed('Authentication credentials were not provided.')

    user, token = user_auth_tuple
    request.user = user
    return user

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
            pdfmetrics.registerFont(TTFont('DejaVuSans', os.path.join(FONTS_DIR, 'DejaVuSans.ttf')))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', os.path.join(FONTS_DIR, 'DejaVuSans-Bold.ttf')))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Oblique', os.path.join(FONTS_DIR, 'DejaVuSans-Oblique.ttf')))
    except Exception as e:
        print(f"Ошибка загрузки шрифтов: {e}")

except ImportError:
    REPORTLAB_AVAILABLE = False

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

class MembershipTypeViewSet(BaseViewSet):
    queryset = MembershipType.objects.all()
    serializer_class = MembershipTypeSerializer

class AttendanceViewSet(BaseViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer

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
    styles = getSampleStyleSheet()

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

    styles.add(ParagraphStyle(
        name='CustomSubtitle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=TA_CENTER
    ))

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

    styles.add(ParagraphStyle(
        name='CustomNormal',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=12
    ))

    return styles


def create_report_header(elements, title, subtitle, styles):
    elements.append(Paragraph(title, styles['CustomTitle']))
    elements.append(Paragraph(subtitle, styles['CustomSubtitle']))
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor('#27ae60'),
        spaceBefore=5,
        spaceAfter=15
    ))


def create_summary_box(elements, summary_items, styles):
    data = []
    for item in summary_items:
        data.append([
            Paragraph(f"<b>{item['label']}:</b>", styles['SummaryText']),
            Paragraph(str(item['value']), styles['SummaryText'])
        ])

    table = Table(data, colWidths=[8 * cm, 8 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),

        # header
        ('FONTNAME', (0, 0), (-1, 0), FONT_NAME_BOLD),

        # тело таблицы ← ВАЖНО
        ('FONTNAME', (0, 1), (-1, -1), FONT_NAME),

        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),

        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
            colors.white, colors.HexColor('#f8f9fa')
        ]),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))


def create_data_table(headers, rows, col_widths):
    table = Table([headers] + rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),

        # header
        ('FONTNAME', (0, 0), (-1, 0), FONT_NAME_BOLD),

        # тело таблицы ← ВАЖНО
        ('FONTNAME', (0, 1), (-1, -1), FONT_NAME),

        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),

        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
            colors.white, colors.HexColor('#f8f9fa')
        ]),
    ]))

    return table


def create_pdf_document(title, subtitle, summary, headers, rows, col_widths):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title
    )

    styles = get_custom_styles()
    elements = []

    create_report_header(elements, title, subtitle, styles)

    if summary:
        create_summary_box(elements, summary, styles)

    elements.append(Paragraph("Детализация", styles['SectionHeader']))
    elements.append(Spacer(1, 0.3 * cm))

    elements.append(create_data_table(headers, rows, col_widths))

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        f"Отчёт сформирован автоматически • {date.today().strftime('%d.%m.%Y')}",
        ParagraphStyle(
            'Footer',
            parent=styles['CustomNormal'],
            fontSize=8,
            textColor=colors.HexColor('#95a5a6'),
            alignment=TA_CENTER
        )
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer



def revenue_report(request):
    try:
        user = jwt_authenticate(request)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=401)
    from .models import Payment

    payments = Payment.objects.select_related('client').order_by('-payment_date')
    total = sum(float(p.amount) for p in payments)

    summary = [
        {'label': 'Общая выручка', 'value': f"{total:,.2f} ₽"},
        {'label': 'Всего платежей', 'value': payments.count()}
    ]

    headers = ['Дата', 'Клиент', 'Сумма', 'Тип оплаты']
    rows = [[
        p.payment_date.strftime('%d.%m.%Y %H:%M'),
        f"{p.client.surname} {p.client.name}",
        f"{float(p.amount):,.2f} ₽",
        p.payment_type
    ] for p in payments]

    pdf = create_pdf_document(
        title="ФИНАНСОВЫЙ ОТЧЁТ",
        subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')}",
        summary=summary,
        headers=headers,
        rows=rows,
        col_widths=[4 * cm, 5 * cm, 3 * cm, 4 * cm]
    )

    return FileResponse(
        pdf,
        as_attachment=True,
        filename='revenue_report.pdf',
        content_type='application/pdf'
    )



def attendance_report(request):
    try:
        user = jwt_authenticate(request)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=401)
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
        pdf = create_pdf_document(
            title="ОТЧЁТ ПО ПОСЕЩАЕМОСТИ",
            subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')}",
            summary=summary_items,
            headers=headers,
            rows=data_rows,
            col_widths=col_widths
        )

        return FileResponse(
            pdf,
            as_attachment=True,
            filename='revenue_report.pdf',
            content_type='application/pdf'
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



def trainer_performance_report(request):
    try:
        user = jwt_authenticate(request)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=401)
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
        pdf = create_pdf_document(
            title="ЭФФЕКТИВНОСТЬ ТРЕНЕРОВ",
            subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')}",
            summary=summary_items,
            headers=headers,
            rows=data_rows,
            col_widths=col_widths
        )

        return FileResponse(
            pdf,
            as_attachment=True,
            filename='revenue_report.pdf',
            content_type='application/pdf'
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



def expiring_memberships_report(request):
    try:
        user = jwt_authenticate(request)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=401)
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
        pdf = create_pdf_document(
            title="ИСТЕКАЮЩИЕ АБОНЕМЕНТЫ",
            subtitle=f"Дата формирования: {date.today().strftime('%d.%m.%Y')} • Проверка на {soon.strftime('%d.%m.%Y')}",
            summary=summary_items,
            headers=headers,
            rows=data_rows,
            col_widths=col_widths
        )

        return FileResponse(
            pdf,
            as_attachment=True,
            filename='revenue_report.pdf',
            content_type='application/pdf'
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Ошибка генерации PDF: {error_detail}")
        return Response(
            {'error': f'Ошибка генерации PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )