
from io import BytesIO
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action, permission_classes, api_view
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


font_config = FontConfiguration()


def get_base_css():
    """Базовые стили для PDF"""
    return weasyprint.CSS(string='''
        @page { margin: 2cm; }
        body { font-family: DejaVu Sans, sans-serif; font-size: 12pt; }
        h1 { color: #2c3e50; border-bottom: 2px solid #27ae60; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background-color: #34495e; color: white; padding: 10px; text-align: left; }
        td { padding: 8px; border-bottom: 1px solid #ddd; }
        tr:nth-child(even) { background-color: #f9f9f9; }
    ''', font_config=font_config)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_report(request):
    """Финансовый отчёт"""
    from .models import Payment

    payments = Payment.objects.select_related('client').all()

    total = sum(float(p.amount) for p in payments)

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Финансовый отчёт</title>
    </head>
    <body>
        <h1>Финансовый отчёт</h1>
        <p><strong>Общая выручка:</strong> {total:,.2f} ₽</p>

        <table>
            <thead>
                <tr>
                    <th>Дата</th>
                    <th>Клиент</th>
                    <th>Сумма</th>
                    <th>Тип оплаты</th>
                </tr>
            </thead>
            <tbody>
    '''

    for p in payments:
        html_content += f'''
                <tr>
                    <td>{p.payment_date.strftime('%d.%m.%Y')}</td>
                    <td>{p.client.surname} {p.client.name}</td>
                    <td>{float(p.amount):,.2f} ₽</td>
                    <td>{p.payment_type}</td>
                </tr>
        '''

    html_content += '''
            </tbody>
        </table>
    </body>
    </html>
    '''

    # Генерация PDF
    pdf_file = BytesIO()
    weasyprint.HTML(string=html_content).write_pdf(
        pdf_file,
        stylesheets=[get_base_css()],
        font_config=font_config
    )
    pdf_file.seek(0)

    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="revenue_report.pdf"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_report(request):
    """Отчёт по посещаемости"""
    from .models import Attendance, Training

    attendances = Attendance.objects.select_related(
        'client', 'training', 'training__trainer'
    ).filter(status='Посетил')

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Отчёт по посещаемости</title>
    </head>
    <body>
        <h1>Отчёт по посещаемости</h1>
        <p><strong>Всего посещений:</strong> {attendances.count()}</p>

        <table>
            <thead>
                <tr>
                    <th>Дата</th>
                    <th>Клиент</th>
                    <th>Тренировка</th>
                    <th>Тренер</th>
                </tr>
            </thead>
            <tbody>
    '''

    for a in attendances:
        html_content += f'''
                <tr>
                    <td>{a.training.date_time.strftime('%d.%m.%Y %H:%M')}</td>
                    <td>{a.client.surname} {a.client.name}</td>
                    <td>{a.training.training_type.name}</td>
                    <td>{a.training.trainer.surname} {a.training.trainer.name}</td>
                </tr>
        '''

    html_content += '''
            </tbody>
        </table>
    </body>
    </html>
    '''

    pdf_file = BytesIO()
    weasyprint.HTML(string=html_content).write_pdf(
        pdf_file,
        stylesheets=[get_base_css()],
        font_config=font_config
    )
    pdf_file.seek(0)

    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trainer_performance_report(request):
    """Отчёт по эффективности тренеров"""
    from .models import Trainer, Training
    from django.db.models import Count

    trainers = Trainer.objects.annotate(
        training_count=Count('training')
    ).order_by('-training_count')

    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Эффективность тренеров</title>
    </head>
    <body>
        <h1>Эффективность тренеров</h1>

        <table>
            <thead>
                <tr>
                    <th>Тренер</th>
                    <th>Специализация</th>
                    <th>Количество тренировок</th>
                </tr>
            </thead>
            <tbody>
    '''

    for t in trainers:
        html_content += f'''
                <tr>
                    <td>{t.surname} {t.name}</td>
                    <td>{t.specialization}</td>
                    <td>{t.training_count}</td>
                </tr>
        '''

    html_content += '''
            </tbody>
        </table>
    </body>
    </html>
    '''

    pdf_file = BytesIO()
    weasyprint.HTML(string=html_content).write_pdf(
        pdf_file,
        stylesheets=[get_base_css()],
        font_config=font_config
    )
    pdf_file.seek(0)

    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="trainer_performance.pdf"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiring_memberships_report(request):
    """Отчёт по истекающим абонементам"""
    from .models import Membership
    from datetime import date, timedelta

    soon = date.today() + timedelta(days=7)
    expiring = Membership.objects.filter(
        end_date__lte=soon,
        status='Активен'
    ).select_related('client', 'type')

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Истекающие абонементы</title>
    </head>
    <body>
        <h1>Истекающие абонементы</h1>
        <p><strong>Критических абонементов:</strong> {expiring.count()}</p>

        <table>
            <thead>
                <tr>
                    <th>Клиент</th>
                    <th>Тип абонемента</th>
                    <th>Дата окончания</th>
                    <th>Осталось дней</th>
                </tr>
            </thead>
            <tbody>
    '''

    for m in expiring:
        days_left = (m.end_date - date.today()).days
        html_content += f'''
                <tr>
                    <td>{m.client.surname} {m.client.name}</td>
                    <td>{m.type.name}</td>
                    <td>{m.end_date.strftime('%d.%m.%Y')}</td>
                    <td>{days_left}</td>
                </tr>
        '''

    html_content += '''
            </tbody>
        </table>
    </body>
    </html>
    '''

    pdf_file = BytesIO()
    weasyprint.HTML(string=html_content).write_pdf(
        pdf_file,
        stylesheets=[get_base_css()],
        font_config=font_config
    )
    pdf_file.seek(0)

    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="expiring_memberships.pdf"'
    return response