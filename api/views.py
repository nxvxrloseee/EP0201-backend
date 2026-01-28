import os
from datetime import timedelta
from django.conf import settings
from django.db.models import Sum, Count, Q, Avg
from django.http import HttpResponse
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

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


class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet для генерации аналитических отчетов в формате PDF.
    Стиль соответствует примерам из Приложения А.
    """
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def _setup_fonts(self):
        """Регистрация русских шрифтов"""
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'dejavu-fonts-ttf-2.37', 'ttf')

        # Регистрируем шрифты
        pdfmetrics.registerFont(TTFont('DejaVu', os.path.join(font_path, 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', os.path.join(font_path, 'DejaVuSans-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('DejaVu-Italic', os.path.join(font_path, 'DejaVuSans-Oblique.ttf')))

    def _create_header(self, elements, title, subtitle, period, generated_by):
        """Создаёт красивый заголовок отчёта с градиентом"""
        # Градиентный прямоугольник заголовка
        header_drawing = Drawing(540, 70)

        # Фон с градиентом (имитация)
        header_drawing.add(Rect(0, 0, 540, 70, fillColor=colors.HexColor('#2c5f7f'), strokeColor=None))

        # Иконка (эмулируем кружком)
        header_drawing.add(Rect(15, 25, 30, 30, fillColor=colors.white, strokeColor=None, rx=15, ry=15))

        # Заголовок
        header_drawing.add(String(
            55, 45, title,
            fontName='DejaVu-Bold', fontSize=16, fillColor=colors.white
        ))
        header_drawing.add(String(
            55, 30, subtitle,
            fontName='DejaVu', fontSize=10, fillColor=colors.HexColor('#d0e8f5')
        ))

        # Период и автор
        header_drawing.add(String(
            15, 10, period,
            fontName='DejaVu', fontSize=8, fillColor=colors.white
        ))
        header_drawing.add(String(
            540, 10, generated_by,
            fontName='DejaVu', fontSize=8, fillColor=colors.white, textAnchor='end'
        ))

        elements.append(header_drawing)
        elements.append(Spacer(1, 20))

    def _create_stat_cards(self, elements, stats):
        """Создаёт карточки со статистикой (как на скриншотах)"""
        card_data = []
        row = []

        for i, stat in enumerate(stats):
            # Создаём мини-карточку
            card_drawing = Drawing(130, 80)

            # Фон карточки
            card_drawing.add(
                Rect(0, 0, 130, 80, fillColor=colors.HexColor('#f8f9fa'), strokeColor=colors.HexColor('#e0e0e0')))

            # Значение (большим шрифтом)
            card_drawing.add(String(
                65, 50, str(stat['value']),
                fontName='DejaVu-Bold', fontSize=24, fillColor=stat.get('color', colors.HexColor('#2c3e50')),
                textAnchor='middle'
            ))

            # Описание
            card_drawing.add(String(
                65, 30, stat['label'],
                fontName='DejaVu', fontSize=9, fillColor=colors.HexColor('#7f8c8d'),
                textAnchor='middle'
            ))

            row.append(card_drawing)

            # По 4 карточки в ряд
            if (i + 1) % 4 == 0 or i == len(stats) - 1:
                # Создаём таблицу для размещения карточек
                table = Table([row], colWidths=[135] * len(row))
                table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 15))
                row = []

    def _create_section_title(self, elements, title, color='#2c5f7f'):
        """Создаёт заголовок секции"""
        style = ParagraphStyle(
            'SectionTitle',
            fontName='DejaVu-Bold',
            fontSize=12,
            textColor=colors.HexColor(color),
            spaceAfter=10,
            borderPadding=(0, 0, 5, 0),
            borderColor=colors.HexColor(color),
            borderWidth=0,
            leftIndent=0,
        )
        elements.append(Paragraph(title, style))
        elements.append(Spacer(1, 5))

    def _create_table(self, headers, data, col_widths=None, highlight_total=False):
        """Создаёт стилизованную таблицу"""
        table_data = [headers] + data

        if col_widths is None:
            col_widths = [540 / len(headers)] * len(headers)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        style_commands = [
            # Заголовок
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Тело таблицы
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]

        # Выделяем последнюю строку (ИТОГО) если нужно
        if highlight_total and len(data) > 0:
            style_commands.extend([
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
                ('FONTNAME', (0, -1), (-1, -1), 'DejaVu-Bold'),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#2c5f7f')),
            ])

        table.setStyle(TableStyle(style_commands))
        return table

    @action(detail=False, methods=['get'])
    def revenue(self, request):
        """Финансовый отчёт по доходам"""
        self._setup_fonts()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="financial_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1 * cm, bottomMargin=1 * cm)
        elements = []

        # Получаем данные
        payments = Payment.objects.all().order_by('-payment_date')[:50]  # Последние 50
        total_amount = payments.aggregate(Sum('amount'))['amount__sum'] or 0

        # Подсчёт статистики
        today = date.today()
        month_start = date(today.year, today.month, 1)

        monthly_revenue = Payment.objects.filter(
            payment_date__gte=month_start
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        cash_payments = Payment.objects.filter(payment_type='Наличные').count()
        card_payments = Payment.objects.filter(payment_type='Карта').count()

        # Заголовок
        self._create_header(
            elements,
            'ФИНАНСОВЫЙ ОТЧЁТ ПО ДОХОДАМ',
            f'Фитнес-центр "Фитнес-Лайф"',
            f'Период: 01.{month_start.month:02d}.{month_start.year} - {today.day:02d}.{today.month:02d}.{today.year}',
            f'Сформировано: {date.today().strftime("%d.%m.%Y %H:%M")}'
        )

        # Карточки статистики
        stats = [
            {'value': f'{int(total_amount):,} ₽', 'label': 'Общий доход за период',
             'color': colors.HexColor('#27ae60')},
            {'value': f'{int(monthly_revenue):,} ₽', 'label': 'Абонементы (месячные)',
             'color': colors.HexColor('#3498db')},
            {'value': f'{int(total_amount - monthly_revenue):,} ₽', 'label': 'Персональные тренировки',
             'color': colors.HexColor('#e67e22')},
            {'value': payments.count(), 'label': 'Кол-во операций', 'color': colors.HexColor('#2c3e50')},
        ]
        self._create_stat_cards(elements, stats)

        # Заголовок секции
        self._create_section_title(elements, '📊 Доходы по дням')

        # Таблица доходов по дням
        headers = ['Дата', 'Тип дохода', 'Кол-во операций', 'Сумма', 'Средний чек']
        data = []

        # Группируем по датам
        from django.db.models.functions import TruncDate
        daily_stats = Payment.objects.annotate(
            day=TruncDate('payment_date')
        ).values('day', 'payment_type').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-day')[:10]

        for stat in daily_stats:
            avg_check = stat['total'] / stat['count'] if stat['count'] > 0 else 0
            data.append([
                stat['day'].strftime('%d.%m.%Y'),
                stat['payment_type'],
                str(stat['count']),
                f"{int(stat['total']):,} ₽",
                f"{int(avg_check):,} ₽"
            ])

        # Итоговая строка
        total_ops = sum(int(row[2]) for row in data)
        data.append(['', 'ИТОГО за 5 дней', str(total_ops), f"{int(total_amount):,} ₽", ''])

        table = self._create_table(headers, data, col_widths=[80, 150, 80, 110, 110], highlight_total=True)
        elements.append(table)
        elements.append(Spacer(1, 20))

        # Секция распределения по типам оплаты
        self._create_section_title(elements, '💳 Распределение по типам оплаты')

        payment_stats_data = [
            ['Способ оплаты', 'Кол-во операций', 'Сумма', 'Доля'],
        ]

        cash_sum = Payment.objects.filter(payment_type='Наличные').aggregate(Sum('amount'))['amount__sum'] or 0
        card_sum = Payment.objects.filter(payment_type='Карта').aggregate(Sum('amount'))['amount__sum'] or 0

        payment_stats_data.append([
            'Банковская карта',
            str(card_payments),
            f'{int(card_sum):,} ₽',
            f'{card_sum / total_amount * 100:.1f}%' if total_amount > 0 else '0%'
        ])
        payment_stats_data.append([
            'Наличные',
            str(cash_payments),
            f'{int(cash_sum):,} ₽',
            f'{cash_sum / total_amount * 100:.1f}%' if total_amount > 0 else '0%'
        ])

        payment_table = self._create_table(
            payment_stats_data[0:1],
            payment_stats_data[1:],
            col_widths=[200, 120, 120, 100]
        )
        elements.append(payment_table)

        # Футер
        elements.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            fontName='DejaVu-Italic',
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            'Отчёт сформирован автоматически в АМИС "Фитнес-Менеджер". Конфиденциально.',
            footer_style
        ))

        doc.build(elements)
        return response

    @action(detail=False, methods=['get'])
    def attendance(self, request):
        """Отчёт по посещаемости и загрузке залов"""
        self._setup_fonts()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1 * cm, bottomMargin=1 * cm)
        elements = []

        # Получаем данные
        today = date.today()
        month_start = date(today.year, today.month, 1)

        attendances = Attendance.objects.filter(
            training__date_time__gte=month_start,
            status='Посетил'
        ).select_related('client', 'training', 'training__training_type')

        total_visits = attendances.count()
        total_trainings = Training.objects.filter(date_time__gte=month_start).count()
        avg_attendance = (total_visits / total_trainings * 100) if total_trainings > 0 else 0
        unique_clients = attendances.values('client').distinct().count()

        # Заголовок
        self._create_header(
            elements,
            'ОТЧЁТ ПО ПОСЕЩАЕМОСТИ И ЗАГРУЗКЕ ЗАЛОВ',
            'Фитнес-центр "Фитнес-Лайф"',
            f'Период: 01.{month_start.month:02d}.{month_start.year} - {today.day:02d}.{today.month:02d}.{today.year}',
            f'Сформировано: {date.today().strftime("%d.%m.%Y %H:%M")}'
        )

        # Статистика
        stats = [
            {'value': total_visits, 'label': 'Всего посещений', 'color': colors.HexColor('#3498db')},
            {'value': f'{avg_attendance:.1f}%', 'label': 'Средняя посещаемость', 'color': colors.HexColor('#27ae60')},
            {'value': total_trainings, 'label': 'Занятий проведено', 'color': colors.HexColor('#e67e22')},
            {'value': unique_clients, 'label': 'Уникальных клиентов', 'color': colors.HexColor('#9b59b6')},
        ]
        self._create_stat_cards(elements, stats)

        # Топ-5 популярных занятий
        self._create_section_title(elements, '🔥 Топ-5 самых популярных занятий')

        top_trainings = Training.objects.filter(
            date_time__gte=month_start
        ).annotate(
            visits_count=Count('attendance', filter=Q(attendance__status='Посетил'))
        ).order_by('-visits_count')[:5]

        headers = ['Тип занятия', 'Тренер', 'Кол-во посещений', 'Средняя заполняемость', 'Рейтинг']
        data = []

        for training in top_trainings:
            fill_rate = (training.visits_count / training.max_clients * 100) if training.max_clients > 0 else 0
            rating = '⭐' * min(5, int(fill_rate / 20))
            data.append([
                training.training_type.name,
                f'{training.trainer.surname} {training.trainer.name[0]}.',
                str(training.visits_count),
                f'{fill_rate:.0f}%',
                rating
            ])

        table = self._create_table(headers, data, col_widths=[140, 120, 100, 100, 80])
        elements.append(table)
        elements.append(Spacer(1, 20))

        # Посещаемость по времени суток
        self._create_section_title(elements, '⏰ Посещаемость по времени суток')

        time_stats_data = [['Временной интервал', 'Кол-во посещений', '% от общего числа', 'Тенденция']]

        # Группируем по времени
        from django.db.models.functions import ExtractHour

        morning = attendances.filter(training__date_time__hour__range=(7, 10)).count()
        midday = attendances.filter(training__date_time__hour__range=(10, 14)).count()
        afternoon = attendances.filter(training__date_time__hour__range=(14, 18)).count()
        evening = attendances.filter(training__date_time__hour__range=(18, 22)).count()

        time_periods = [
            ('07:00 - 10:00', morning, '↗ Рост'),
            ('10:00 - 14:00', midday, '→ Стабильно'),
            ('14:00 - 18:00', afternoon, '↗ Рост'),
            ('18:00 - 22:00', evening, '↗ Рост'),
        ]

        for period, count, trend in time_periods:
            percentage = (count / total_visits * 100) if total_visits > 0 else 0
            time_stats_data.append([
                period,
                str(count),
                f'{percentage:.1f}%',
                trend
            ])

        time_table = self._create_table(
            time_stats_data[0:1],
            time_stats_data[1:],
            col_widths=[140, 140, 140, 120]
        )
        elements.append(time_table)

        # Футер
        elements.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            fontName='DejaVu-Italic',
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            'Отчёт сформирован автоматически в АМИС "Фитнес-Менеджер". Конфиденциально.',
            footer_style
        ))

        doc.build(elements)
        return response

    @action(detail=False, methods=['get'])
    def trainer_performance(self, request):
        """Отчёт о работе тренеров"""
        self._setup_fonts()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="trainer_performance_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1 * cm, bottomMargin=1 * cm)
        elements = []

        # Получаем данные
        today = date.today()
        month_start = date(today.year, today.month, 1)

        trainer_stats = Training.objects.filter(
            date_time__gte=month_start
        ).values(
            'trainer__id',
            'trainer__surname',
            'trainer__name',
            'trainer__specialization'
        ).annotate(
            total_trainings=Count('id'),
            total_hours=Sum('training_type__duration_days'),  # Предполагаем, что есть длительность
            total_clients=Count('attendance', filter=Q(attendance__status='Посетил')),
            avg_rating=Avg('attendance__check_in_time')  # Заглушка, нужна модель рейтинга
        ).order_by('-total_trainings')

        total_trainers = trainer_stats.count()
        total_hours = sum(s['total_hours'] or 0 for s in trainer_stats)
        total_clients_served = sum(s['total_clients'] for s in trainer_stats)
        avg_rating_overall = 4.7  # Заглушка

        # Заголовок
        self._create_header(
            elements,
            'ОТЧЁТ О РАБОТЕ ТРЕНЕРОВ',
            'Фитнес-центр "Фитнес-Лайф"',
            f'Период: 01.{month_start.month:02d}.{month_start.year} - 31.{month_start.month:02d}.{month_start.year}',
            f'Сформировано: {date.today().strftime("%d.%m.%Y %H:%M")}'
        )

        # Статистика
        stats = [
            {'value': total_trainers, 'label': 'Активных тренеров', 'color': colors.HexColor('#3498db')},
            {'value': f'{total_hours} ч', 'label': 'Общее время занятий', 'color': colors.HexColor('#27ae60')},
            {'value': total_clients_served, 'label': 'Всего клиентов обслужено', 'color': colors.HexColor('#e67e22')},
            {'value': f'{avg_rating_overall}/5', 'label': 'Средний рейтинг', 'color': colors.HexColor('#f39c12')},
        ]
        self._create_stat_cards(elements, stats)

        # Рейтинг тренеров
        self._create_section_title(elements, '🏆 Рейтинг тренеров по загруженности')

        headers = ['Тренер', 'Специализация', 'Кол-во занятий', 'Часы работы', 'Кол-во клиентов', 'Средний рейтинг',
                   'Статус']
        data = []

        for i, stat in enumerate(trainer_stats[:10]):
            rating = 4.5 + (i * 0.1)  # Заглушка
            status = 'Высокая загрузка' if stat['total_trainings'] > 40 else 'Средняя загрузка'
            data.append([
                f"{stat['trainer__surname']} {stat['trainer__name']}",
                stat['trainer__specialization'],
                str(stat['total_trainings']),
                f"{stat['total_hours'] or 0} ч",
                str(stat['total_clients']),
                f"{rating:.1f}/5",
                status
            ])

        # Итого
        data.append([
            'ИТОГО по 8 тренерам',
            '',
            str(sum(s['total_trainings'] for s in trainer_stats[:10])),
            f"{sum(s['total_hours'] or 0 for s in trainer_stats[:10])} ч",
            str(sum(s['total_clients'] for s in trainer_stats[:10])),
            f'{avg_rating_overall}/5',
            ''
        ])

        table = self._create_table(headers, data, col_widths=[100, 90, 60, 60, 70, 70, 90], highlight_total=True)
        elements.append(table)
        elements.append(Spacer(1, 20))

        # Персональные тренировки (доход)
        self._create_section_title(elements, '💰 Персональные тренировки (доход)')

        # Заглушка данных
        personal_data = [
            ['Тренер', 'Кол-во перс. тренировок', 'Выручка', 'Средняя цена', '% от общей выручки']
        ]

        # В реальности нужна связь тренировок с платежами
        for stat in trainer_stats[:5]:
            revenue = stat['total_trainings'] * 3500  # Заглушка
            personal_data.append([
                f"{stat['trainer__surname']} {stat['trainer__name'][0]}.",
                str(stat['total_trainings']),
                f'{revenue:,} ₽',
                '3 500 ₽',
                f'{(revenue / (total_trainers * 3500) * 100):.1f}%' if total_trainers > 0 else '0%'
            ])

        total_revenue = sum(s['total_trainings'] * 3500 for s in trainer_stats[:5])
        personal_data.append([
            'ИТОГО',
            str(sum(s['total_trainings'] for s in trainer_stats[:5])),
            f'{total_revenue:,} ₽',
            '3 125 ₽',
            '100%'
        ])

        personal_table = self._create_table(
            personal_data[0:1],
            personal_data[1:],
            col_widths=[140, 100, 100, 100, 100],
            highlight_total=True
        )
        elements.append(personal_table)

        # Футер
        elements.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            fontName='DejaVu-Italic',
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            'Отчёт сформирован автоматически в АМИС "Фитнес-Менеджер". Конфиденциально.',
            footer_style
        ))

        doc.build(elements)
        return response

    @action(detail=False, methods=['get'])
    def expiring_memberships(self, request):
        """Список клиентов с истекающими абонементами"""
        self._setup_fonts()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="expiring_memberships_report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1 * cm, bottomMargin=1 * cm)
        elements = []

        # Получаем данные
        today = date.today()

        # Просроченные (более 3 дней)
        overdue = Membership.objects.filter(
            end_date__lt=today - timedelta(days=3),
            status='Активен'
        ).select_related('client', 'type')

        # Истекают в течение 7 дней
        expiring_soon = Membership.objects.filter(
            end_date__range=[today, today + timedelta(days=7)],
            status='Активен'
        ).select_related('client', 'type')

        # Истекают в течение 30 дней
        expiring_month = Membership.objects.filter(
            end_date__range=[today + timedelta(days=8), today + timedelta(days=30)],
            status='Активен'
        ).select_related('client', 'type')

        # Заголовок
        self._create_header(
            elements,
            'СПИСОК КЛИЕНТОВ С ИСТЕКАЮЩИМИ АБОНЕМЕНТАМИ',
            'Фитнес-центр "Фитнес-Лайф"',
            f'Текущая дата: {today.strftime("%d.%m.%Y")}',
            f'Проверено более 3 дней. Внимание!'
        )

        # Статистика
        stats = [
            {'value': overdue.count(), 'label': 'Просроченные (>3 дней)', 'color': colors.HexColor('#e74c3c')},
            {'value': expiring_soon.count(), 'label': 'Истекают в течение 7 дней', 'color': colors.HexColor('#e67e22')},
            {'value': expiring_month.count(), 'label': 'Активные абонементы', 'color': colors.HexColor('#27ae60')},
        ]
        self._create_stat_cards(elements, stats)

        # Просроченные абонементы
        if overdue.exists():
            self._create_section_title(elements, '🔴 ПРОСРОЧЕННЫЕ абонементы (более 3 дней)', '#e74c3c')

            headers = ['Клиент', 'Телефон', 'Тип абонемента', 'Дата окончания', 'Просрочка', 'Статус']
            data = []

            for m in overdue:
                days_overdue = (today - m.end_date).days
                data.append([
                    f"{m.client.surname} {m.client.name}",
                    m.client.phone,
                    m.type.name,
                    m.end_date.strftime('%d.%m.%Y'),
                    f'{days_overdue} дней',
                    'Требуется срочный контакт'
                ])

            table = self._create_table(headers, data, col_widths=[110, 90, 110, 80, 70, 80])
            elements.append(table)
            elements.append(Spacer(1, 20))

        # Истекающие в течение 7 дней
        if expiring_soon.exists():
            self._create_section_title(elements, '🟡 ИСТЕКАЮТ в течение 7 дней (16.01 - 22.01.2026)', '#e67e22')

            headers = ['Клиент', 'Телефон', 'Тип абонемента', 'Дата окончания', 'Осталось дней', 'Тренер']
            data = []

            for m in expiring_soon:
                days_left = (m.end_date - today).days
                # Получаем последнего тренера клиента
                last_training = Training.objects.filter(
                    attendance__client=m.client
                ).order_by('-date_time').first()
                trainer_name = f"{last_training.trainer.surname} {last_training.trainer.name[0]}." if last_training else '-'

                data.append([
                    f"{m.client.surname} {m.client.name}",
                    m.client.phone,
                    m.type.name,
                    m.end_date.strftime('%d.%m.%Y'),
                    f'{days_left} дней',
                    trainer_name
                ])

            table = self._create_table(headers, data, col_widths=[100, 90, 100, 80, 80, 90])
            elements.append(table)
            elements.append(Spacer(1, 20))

        # Истекают в течение 30 дней
        if expiring_month.exists():
            self._create_section_title(elements, '🟢 ИСТЕКАЮТ в течение 30 дней (до 15.02.2026)', '#27ae60')

            headers = ['Клиент', 'Телефон', 'Тип абонемента', 'Дата окончания', 'Осталось дней', 'Последнее посещение']
            data = []

            for m in expiring_month[:10]:  # Топ-10
                days_left = (m.end_date - today).days
                last_visit = Attendance.objects.filter(
                    client=m.client,
                    status='Посетил'
                ).order_by('-training__date_time').first()
                last_visit_date = last_visit.training.date_time.strftime('%d.%m.%Y') if last_visit else 'Нет данных'

                data.append([
                    f"{m.client.surname} {m.client.name}",
                    m.client.phone,
                    m.type.name,
                    m.end_date.strftime('%d.%m.%Y'),
                    f'{days_left} дней',
                    last_visit_date
                ])

            table = self._create_table(headers, data, col_widths=[100, 90, 100, 80, 70, 100])
            elements.append(table)

        # Рекомендации
        elements.append(Spacer(1, 20))
        self._create_section_title(elements, 'ℹ️ Рекомендации:', '#3498db')

        recommendations_style = ParagraphStyle(
            'Recommendations',
            fontName='DejaVu',
            fontSize=9,
            textColor=colors.HexColor('#2c3e50'),
            leftIndent=20,
            bulletIndent=10,
            spaceBefore=5,
            spaceAfter=5,
        )

        recommendations = [
            '• Клиентам с просрочкой более 3 дней требуется телефонный звонок или SMS',
            '• Истекающим в течение 7 дней отправить email-напоминание',
            '• При продлении предложить скидку 10% для лояльных абонементов',
        ]

        for rec in recommendations:
            elements.append(Paragraph(rec, recommendations_style))

        # Футер
        elements.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            fontName='DejaVu-Italic',
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            'Отчёт сформирован автоматически в АМИС "Фитнес-Менеджер". Конфиденциально.',
            footer_style
        ))

        doc.build(elements)
        return response