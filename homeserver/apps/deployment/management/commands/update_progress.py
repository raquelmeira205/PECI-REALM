import os
import re

from django.core.management.base import BaseCommand


FILES = [
    ('templates/deployment/partials/step_1.html', 1),
    ('templates/deployment/partials/step_2.html', 2),
    ('templates/deployment/partials/step_3.html', 3),
    ('templates/deployment/partials/step_3_configure_room.html', 3),
    ('templates/deployment/partials/step_3b_calibrate.html', 4),
]


def get_button_html(step_num, label, current_step, endpoint):
    if step_num < current_step:
        return f'''<button hx-get="{endpoint}" hx-target="#wizard-content" class="px-3 py-1.5 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-lg hover:bg-emerald-100 dark:hover:bg-emerald-800/60 transition-colors border border-emerald-200 dark:border-emerald-700/50 flex items-center gap-2 shadow-sm cursor-pointer">
  <div class="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">✓</div>
  <span>{label}</span>
</button>'''
    if step_num == current_step:
        return f'''<div class="px-3 py-1.5 bg-emerald-600 text-white rounded-lg border border-emerald-500 flex items-center gap-2 shadow-md">
  <div class="w-5 h-5 rounded-full bg-white text-emerald-600 flex items-center justify-center text-[11px] font-bold">{step_num}</div>
  <span>{label}</span>
</div>'''

    return f'''<div class="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 rounded-lg border border-slate-200 dark:border-slate-700 flex items-center gap-2 opacity-70">
  <div class="w-5 h-5 rounded-full bg-slate-300 dark:bg-slate-600 text-slate-500 dark:text-slate-400 flex items-center justify-center text-[11px] font-bold">{step_num}</div>
  <span>{label}</span>
</div>'''


def generate_progress_bar(current_step):
    b1 = get_button_html(1, "Habitação", current_step, "/deployment/api/step1/")
    b2 = get_button_html(2, "Divisões", current_step, "/deployment/api/step2/")
    b3 = get_button_html(3, "Sensores", current_step, "/deployment/api/step3/")
    b4 = get_button_html(4, "Calibração", current_step, "#")

    return f'''<!-- Progress Bar -->
<div class="mb-6 w-full">
  <div class="flex flex-row items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wide w-full overflow-x-auto pb-2 custom-scrollbar">
    {b1}
    <div class="hidden md:block flex-grow h-px bg-slate-300 dark:bg-slate-600 mx-2"></div>
    {b2}
    <div class="hidden md:block flex-grow h-px bg-slate-300 dark:bg-slate-600 mx-2"></div>
    {b3}
    <div class="hidden md:block flex-grow h-px bg-slate-300 dark:bg-slate-600 mx-2"></div>
    {b4}
  </div>
</div>
<!-- End Progress Bar -->'''


def update_progress_templates():
    updated_files = []

    for file_path, current_step in FILES:
        if not os.path.exists(file_path):
            continue

        with open(file_path, 'r', encoding='utf-8') as file_handle:
            content = file_handle.read()

        new_progress_bar = generate_progress_bar(current_step)

        if "<!-- End Progress Bar -->" in content:
            content = re.sub(
                r'<!-- Progress Bar -->.*?<!-- End Progress Bar -->',
                new_progress_bar,
                content,
                flags=re.DOTALL,
            )
        elif "<!-- Progress Bar -->" in content:
            content = re.sub(
                r'<!-- Progress Bar -->\s*<div class="mb-[0-9]">.*?</div>\s*</div>\s*(<div class="mb-[0-9]">|<!-- Header|{# ── Cabeçalho)',
                r'' + new_progress_bar + r'\n\n  \1',
                content,
                flags=re.DOTALL,
            )

            if "step_3b" in file_path:
                content = re.sub(
                    r'<!-- Progress Bar -->\s*<div class="mb-2">.*?</div>\s*</div>\s*{# ── Cabeçalho',
                    r'' + new_progress_bar + r'\n\n  {# ── Cabeçalho',
                    content,
                    flags=re.DOTALL,
                )

        with open(file_path, 'w', encoding='utf-8') as file_handle:
            file_handle.write(content)

        updated_files.append(file_path)

    return updated_files


class Command(BaseCommand):
    help = 'Atualiza a barra de progresso dos templates do wizard de deployment.'

    def handle(self, *args, **kwargs):
        updated_files = update_progress_templates()

        if not updated_files:
            self.stdout.write(self.style.WARNING('Nenhum template foi atualizado.'))
            return

        for file_path in updated_files:
            self.stdout.write(self.style.SUCCESS(f'Updated {file_path}'))