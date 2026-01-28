import os
from datetime import date, timedelta
from django.conf import settings
from django.db.models import Sum, Count, Q, Avg
from django.http import HttpResponse
from django.template import Context, Template
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

# Импорт WeasyPrint
try:
    import weasyprint
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    weasyprint = None

from .serializers import *
from .permissions import IsStaffOrReadOnly

# Шаблон HTML для отчетов
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {
            size: A4;
            margin: 1.5cm;
            @bottom-center {
                content: "Отчёт сформирован автоматически в АМИС «Фитнес-Менеджер». Конфиденциально.";
                font-family: 'DejaVu-Italic', sans-serif;
                font-size: 8pt;
                color: #7f8c8d;
            }
        }
        @font-face {
            font-family: 'DejaVu';
            src: url('file://{{ font_path }}/DejaVuSans.ttf');
        }
        @font-face {
            font-family: 'DejaVu-Bold';
            src: url('file://{{ font_path }}/DejaVuSans-Bold.ttf');
        }
        @font-face {
            font-family: 'DejaVu-Italic';
            src: url('file://{{ font_path }}/DejaVuSans-Oblique.ttf');
        }

        body {
            font-family: 'DejaVu', sans-serif;
            color: #2c3e50;
            font-size: 10pt;
        }

        /* Заголовок */
        .header {
            background-color: #2c5f7f;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            position: relative;
        }
        .header h1 {
            font-family: 'DejaVu-Bold';
            font-size: 16pt;
            margin: 0 0 5px 0;
            text-transform: uppercase;
        }
        .header .subtitle {
            color: #d0e8f5;
            font-size: 10pt;
        }
        .header .meta {
            margin-top: 15px;
            font-size: 8pt;
            display: flex;
            justify-content: space-between;
        }

        /* Карточки статистики */
        .stats-grid {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            margin-bottom: 25px;
        }
        .stat-card {
            background-color: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 15px;
            width: 23%;
            text-align: center;
            box-sizing: border-box;
        }
        .stat-value {
            font-family: 'DejaVu-Bold';
            font-size: 18pt;
            margin-bottom: 5px;
        }
        .stat-label {
            font-size: 9pt;
            color: #7f8c8d;
        }

        /* Секции */
        .section-title {
            font-family: 'DejaVu-Bold';
            font-size: 12pt;
            color: {{ section_color|default:'#2c5f7f' }};
            border-bottom: 2px solid {{ section_color|default:'#2c5f7f' }};
            padding-bottom: 5px;
            margin-top: 30px;
            margin-bottom: 15px;
        }

        /* Таблицы */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th {
            background-color: #34495e;
            color: white;
            font-family: 'DejaVu-Bold';
            font-size: 9pt;
            padding: 10px;
            text-align: left;
        }
        td {
            padding: 8px 10px;
            border-bottom: 1px solid #dee2e6;
            font-size: 9pt;
        }
        tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        tr.total-row td {
            background-color: #e8f4f8;
            font-family: 'DejaVu-Bold';
            border-top: 2px solid #2c5f7f;
        }

        /* Рекомендации */
        .recommendations {
            background-color: #f0f8ff;
            border-left: 4px solid #3498db;
            padding: 15px;
            font-size: 9pt;
            margin-top: 10px;
        }
        .recommendations ul {
            margin: 0;
            padding-left: 20px;
        }
        .recommendations li {
            margin-bottom: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }}</h1>
        <div class="subtitle">{{ subtitle }}</div>
        <div class="meta">
            <span>{{ period_label }}</span>
            <span>{{ generated_by }}</span>
        </div>
    </div>

    {% if stats %}
    <div class="stats-grid">
        {% for stat in stats %}
        <div class="stat-card">
            <div class="stat-value" style="color: {{ stat.color|default:'#2c3e50' }}">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% for section in content_sections %}
        {% if section.title %}
            <div class="section-title" style="color: {{ section.color|default:'#2c5f7f' }}; border-color: {{ section.color|default:'#2c5f7f' }};">
                {{ section.title }}
            </div>
        {% endif %}

        {% if section.type == 'table' %}
        <table>
            <thead>
                <tr>
                    {% for header in section.headers %}
                    <th>{{ header }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in section.rows %}
                <tr class="{% if section.has_total and forloop.last %}total-row{% endif %}">
                    {% for cell in row %}
                    <td>{{ cell }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% elif section.type == 'list' %}
        <div class="recommendations">
            <ul>
                {% for item in section.items %}
                <li>{{ item }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
    {% endfor %}
</body>
</html>
"""


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
    ViewSet для генерации аналитических отчетов в формате PDF с использованием WeasyPrint.
    Стиль соответствует примерам из МП (Макетирование).
    """
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]

    def _get_font_path(self):
        return os.path.join(settings.BASE_DIR, 'static', 'fonts', 'dejavu-fonts-ttf-2.37', 'ttf')

    def _render_pdf(self, context, filename):
        if not weasyprint:
            return Response({'error': 'WeasyPrint not installed on server'}, status=500)

        # Добавляем путь к шрифтам в контекст
        context['font_path'] = self._get_font_path()

        # Рендеринг HTML из строкового шаблона
        template = Template(REPORT_TEMPLATE)
        html_content = template.render(Context(context))

        # Генерация PDF
        font_config = FontConfiguration()
        pdf_file = weasyprint.HTML(string=html_content, base_url=str(settings.BASE_DIR)).write_pdf(
            font_config=font_config)

        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'])
    def revenue(self, request):
        """Финансовый отчёт по доходам"""
        today = date.today()
        month_start = date(today.year, today.month, 1)

        # Получаем данные
        payments = Payment.objects.all().order_by('-payment_date')[:50]
        total_amount = payments.aggregate(Sum('amount'))['amount__sum'] or 0

        monthly_revenue = Payment.objects.filter(
            payment_date__gte=month_start
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        cash_payments = Payment.objects.filter(payment_type='Наличные').count()
        card_payments = Payment.objects.filter(payment_type='Карта').count()
        cash_sum = Payment.objects.filter(payment_type='Наличные').aggregate(Sum('amount'))['amount__sum'] or 0
        card_sum = Payment.objects.filter(payment_type='Карта').aggregate(Sum('amount'))['amount__sum'] or 0

        # Таблица по дням
        from django.db.models.functions import TruncDate
        daily_stats = Payment.objects.annotate(
            day=TruncDate('payment_date')
        ).values('day', 'payment_type').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-day')[:10]

        daily_rows = []
        for stat in daily_stats:
            avg_check = stat['total'] / stat['count'] if stat['count'] > 0 else 0
            daily_rows.append([
                stat['day'].strftime('%d.%m.%Y'),
                stat['payment_type'],
                str(stat['count']),
                f"{int(stat['total']):,} ₽",
                f"{int(avg_check):,} ₽"
            ])

        # Итоговая строка
        total_ops_table = sum(int(row[2]) for row in daily_rows)
        daily_rows.append(['', 'ИТОГО за 10 дней', str(total_ops_table), f"{int(total_amount):,} ₽", ''])

        # Таблица распределения
        payment_type_rows = [
            ['Банковская карта', str(card_payments), f'{int(card_sum):,} ₽',
             f'{card_sum / total_amount * 100:.1f}%' if total_amount else '0%'],
            ['Наличные', str(cash_payments), f'{int(cash_sum):,} ₽',
             f'{cash_sum / total_amount * 100:.1f}%' if total_amount else '0%'],
        ]

        context = {
            'title': 'ФИНАНСОВЫЙ ОТЧЁТ ПО ДОХОДАМ',
            'subtitle': 'Фитнес-центр "Фитнес-Лайф"',
            'period_label': f'Период: 01.{month_start.month:02d}.{month_start.year} - {today.day:02d}.{today.month:02d}.{today.year}',
            'generated_by': f'Сформировано: {date.today().strftime("%d.%m.%Y %H:%M")}',
            'stats': [
                {'value': f'{int(total_amount):,} ₽', 'label': 'Общий доход', 'color': '#27ae60'},
                {'value': f'{int(monthly_revenue):,} ₽', 'label': 'Абонементы (мес.)', 'color': '#3498db'},
                {'value': f'{int(total_amount - monthly_revenue):,} ₽', 'label': 'Перс. тренировки',
                 'color': '#e67e22'},
                {'value': payments.count(), 'label': 'Операций', 'color': '#2c3e50'},
            ],
            'content_sections': [
                {
                    'title': '📊 Доходы по дням',
                    'type': 'table',
                    'headers': ['Дата', 'Тип дохода', 'Кол-во операций', 'Сумма', 'Средний чек'],
                    'rows': daily_rows,
                    'has_total': True
                },
                {
                    'title': '💳 Распределение по типам оплаты',
                    'type': 'table',
                    'headers': ['Способ оплаты', 'Кол-во операций', 'Сумма', 'Доля'],
                    'rows': payment_type_rows,
                    'has_total': False
                }
            ]
        }

        return self._render_pdf(context, 'financial_report.pdf')

    @action(detail=False, methods=['get'])
    def attendance(self, request):
        """Отчёт по посещаемости и загрузке залов"""
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

        # Топ 5
        top_trainings = Training.objects.filter(
            date_time__gte=month_start
        ).annotate(
            visits_count=Count('attendance', filter=Q(attendance__status='Посетил'))
        ).order_by('-visits_count')[:5]

        top_rows = []
        for t in top_trainings:
            fill_rate = (t.visits_count / t.max_clients * 100) if t.max_clients > 0 else 0
            rating = '⭐' * min(5, int(fill_rate / 20))
            top_rows.append([
                t.training_type.name,
                f'{t.trainer.surname} {t.trainer.name[0]}.',
                str(t.visits_count),
                f'{fill_rate:.0f}%',
                rating
            ])

        # По времени суток (упрощенно)
        morning = attendances.filter(training__date_time__hour__range=(7, 10)).count()
        midday = attendances.filter(training__date_time__hour__range=(10, 14)).count()
        afternoon = attendances.filter(training__date_time__hour__range=(14, 18)).count()
        evening = attendances.filter(training__date_time__hour__range=(18, 22)).count()

        time_rows = [
            ['07:00 - 10:00', str(morning), f'{(morning / total_visits * 100):.1f}%' if total_visits else '0%',
             '↗ Рост'],
            ['10:00 - 14:00', str(midday), f'{(midday / total_visits * 100):.1f}%' if total_visits else '0%',
             '→ Стабильно'],
            ['14:00 - 18:00', str(afternoon), f'{(afternoon / total_visits * 100):.1f}%' if total_visits else '0%',
             '↗ Рост'],
            ['18:00 - 22:00', str(evening), f'{(evening / total_visits * 100):.1f}%' if total_visits else '0%',
             '↗ Рост'],
        ]

        context = {
            'title': 'ОТЧЁТ ПО ПОСЕЩАЕМОСТИ',
            'subtitle': 'Фитнес-центр "Фитнес-Лайф"',
            'period_label': f'Период: 01.{month_start.month:02d}.{month_start.year} - {today.day:02d}.{today.month:02d}.{today.year}',
            'generated_by': f'Сформировано: {date.today().strftime("%d.%m.%Y %H:%M")}',
            'stats': [
                {'value': total_visits, 'label': 'Всего посещений', 'color': '#3498db'},
                {'value': f'{avg_attendance:.1f}%', 'label': 'Средняя посещаемость', 'color': '#27ae60'},
                {'value': total_trainings, 'label': 'Занятий проведено', 'color': '#e67e22'},
                {'value': unique_clients, 'label': 'Уникальных клиентов', 'color': '#9b59b6'},
            ],
            'content_sections': [
                {
                    'title': '🔥 Топ-5 популярных занятий',
                    'type': 'table',
                    'headers': ['Тип занятия', 'Тренер', 'Кол-во посещений', 'Заполняемость', 'Рейтинг'],
                    'rows': top_rows
                },
                {
                    'title': '⏰ Посещаемость по времени суток',
                    'type': 'table',
                    'headers': ['Интервал', 'Кол-во посещений', '% от общего', 'Тенденция'],
                    'rows': time_rows
                }
            ]
        }

        return self._render_pdf(context, 'attendance_report.pdf')

    @action(detail=False, methods=['get'])
    def trainer_performance(self, request):
        """Отчёт о работе тренеров"""
        today = date.today()
        month_start = date(today.year, today.month, 1)

        trainer_stats = Training.objects.filter(
            date_time__gte=month_start
        ).values(
            'trainer__id', 'trainer__surname', 'trainer__name', 'trainer__specialization'
        ).annotate(
            total_trainings=Count('id'),
            total_hours=Sum('training_type__duration_days'),
            total_clients=Count('attendance', filter=Q(attendance__status='Посетил')),
        ).order_by('-total_trainings')

        total_trainers = trainer_stats.count()
        total_hours = sum(s['total_hours'] or 0 for s in trainer_stats)
        total_clients_served = sum(s['total_clients'] for s in trainer_stats)

        trainer_rows = []
        for i, stat in enumerate(trainer_stats[:10]):
            status_text = 'Высокая загрузка' if stat['total_trainings'] > 40 else 'Средняя загрузка'
            trainer_rows.append([
                f"{stat['trainer__surname']} {stat['trainer__name']}",
                stat['trainer__specialization'],
                str(stat['total_trainings']),
                f"{stat['total_hours'] or 0} ч",
                str(stat['total_clients']),
                "4.8/5",  # Заглушка
                status_text
            ])

        # Итого по тренерам
        trainer_rows.append([
            'ИТОГО', '',
            str(sum(s['total_trainings'] for s in trainer_stats[:10])),
            f"{sum(s['total_hours'] or 0 for s in trainer_stats[:10])} ч",
            str(sum(s['total_clients'] for s in trainer_stats[:10])),
            '-', ''
        ])

        # Персональные (заглушка)
        personal_rows = []
        for stat in trainer_stats[:5]:
            revenue = stat['total_trainings'] * 3500
            personal_rows.append([
                f"{stat['trainer__surname']} {stat['trainer__name'][0]}.",
                str(stat['total_trainings']),
                f'{revenue:,} ₽',
                '3 500 ₽',
                '10%'  # Заглушка
            ])

        context = {
            'title': 'ОТЧЁТ О РАБОТЕ ТРЕНЕРОВ',
            'subtitle': 'Фитнес-центр "Фитнес-Лайф"',
            'period_label': f'Период: 01.{month_start.month:02d}.{month_start.year} - {today.day:02d}.{today.month:02d}.{today.year}',
            'generated_by': f'Сформировано: {date.today().strftime("%d.%m.%Y %H:%M")}',
            'stats': [
                {'value': total_trainers, 'label': 'Активных тренеров', 'color': '#3498db'},
                {'value': f'{total_hours} ч', 'label': 'Общее время', 'color': '#27ae60'},
                {'value': total_clients_served, 'label': 'Клиентов обслужено', 'color': '#e67e22'},
                {'value': '4.7/5', 'label': 'Средний рейтинг', 'color': '#f39c12'},
            ],
            'content_sections': [
                {
                    'title': '🏆 Рейтинг тренеров по загруженности',
                    'type': 'table',
                    'headers': ['Тренер', 'Специализация', 'Занятий', 'Часы', 'Клиенты', 'Рейтинг', 'Статус'],
                    'rows': trainer_rows,
                    'has_total': True
                },
                {
                    'title': '💰 Персональные тренировки (доход)',
                    'type': 'table',
                    'headers': ['Тренер', 'Кол-во', 'Выручка', 'Ср. цена', '% выручки'],
                    'rows': personal_rows
                }
            ]
        }

        return self._render_pdf(context, 'trainer_report.pdf')

    @action(detail=False, methods=['get'])
    def expiring_memberships(self, request):
        """Список клиентов с истекающими абонементами"""
        today = date.today()

        # Данные
        overdue = Membership.objects.filter(
            end_date__lt=today - timedelta(days=3),
            status='Активен'
        ).select_related('client', 'type')

        expiring_soon = Membership.objects.filter(
            end_date__range=[today, today + timedelta(days=7)],
            status='Активен'
        ).select_related('client', 'type')

        expiring_month = Membership.objects.filter(
            end_date__range=[today + timedelta(days=8), today + timedelta(days=30)],
            status='Активен'
        ).select_related('client', 'type')

        sections = []

        if overdue.exists():
            rows = []
            for m in overdue:
                rows.append([
                    f"{m.client.surname} {m.client.name}",
                    m.client.phone, m.type.name,
                    m.end_date.strftime('%d.%m.%Y'),
                    f'{(today - m.end_date).days} дней',
                    'Срочный контакт'
                ])
            sections.append({
                'title': '🔴 ПРОСРОЧЕННЫЕ (более 3 дней)',
                'color': '#e74c3c',
                'type': 'table',
                'headers': ['Клиент', 'Телефон', 'Абонемент', 'Дата окончания', 'Просрочка', 'Действие'],
                'rows': rows
            })

        if expiring_soon.exists():
            rows = []
            for m in expiring_soon:
                rows.append([
                    f"{m.client.surname} {m.client.name}",
                    m.client.phone, m.type.name,
                    m.end_date.strftime('%d.%m.%Y'),
                    f'{(m.end_date - today).days} дней'
                ])
            sections.append({
                'title': '🟡 ИСТЕКАЮТ в течение 7 дней',
                'color': '#e67e22',
                'type': 'table',
                'headers': ['Клиент', 'Телефон', 'Абонемент', 'Дата окончания', 'Осталось'],
                'rows': rows
            })

        if expiring_month.exists():
            rows = []
            for m in expiring_month[:10]:
                rows.append([
                    f"{m.client.surname} {m.client.name}",
                    m.client.phone, m.type.name,
                    m.end_date.strftime('%d.%m.%Y'),
                    f'{(m.end_date - today).days} дней'
                ])
            sections.append({
                'title': '🟢 ИСТЕКАЮТ в течение 30 дней',
                'color': '#27ae60',
                'type': 'table',
                'headers': ['Клиент', 'Телефон', 'Абонемент', 'Дата окончания', 'Осталось'],
                'rows': rows
            })

        sections.append({
            'title': 'ℹ️ Рекомендации',
            'type': 'list',
            'color': '#3498db',
            'items': [
                'Клиентам с просрочкой более 3 дней требуется звонок',
                'Истекающим в течение 7 дней отправить email/SMS напоминание',
                'При продлении предложить скидку 5% за лояльность'
            ]
        })

        context = {
            'title': 'ИСТЕКАЮЩИЕ АБОНЕМЕНТЫ',
            'subtitle': 'Фитнес-центр "Фитнес-Лайф"',
            'period_label': f'Текущая дата: {today.strftime("%d.%m.%Y")}',
            'generated_by': 'Внимание! Требуется обработка.',
            'stats': [
                {'value': overdue.count(), 'label': 'Просрочено (>3 дн)', 'color': '#e74c3c'},
                {'value': expiring_soon.count(), 'label': 'Истекают (7 дн)', 'color': '#e67e22'},
                {'value': expiring_month.count(), 'label': 'Истекают (30 дн)', 'color': '#27ae60'},
            ],
            'content_sections': sections
        }

        return self._render_pdf(context, 'expiring_report.pdf')