-- Seed data for expense_accounts
INSERT INTO expense_accounts (code, name, description, default_deductible_pct, active) VALUES
('ADMIN_GEN',     'הוצאות הנהלה וכלליות / General Administrative Expenses', 'General overhead and administrative costs', 100.00, TRUE),
('PROF_SERV',     'שירותים מקצועיים / Professional Services',              'Accountants, legal, or consulting services', 100.00, TRUE),
('TRAVEL',        'נסיעות / Travel',                                        'Transportation, taxis, fuel, business trips', 75.00, TRUE),
('VEHICLE',       'אחזקת רכב / Vehicle Maintenance',                        'Fuel, repairs, maintenance, insurance', 50.00, TRUE),
('RENT_UTIL',     'ארנונה, חשמל ומים / Rent, Electricity & Water',          'Utilities, electricity, water, and municipal tax', 100.00, TRUE),
('DONATIONS',     'תרומות / Donations',                                     'Charitable donations and contributions', 0.00, TRUE),
('ENTERTAIN',     'בשילמות וספרות מקצועית / Meals & Professional Materials','Professional literature, meals, and representation', 50.00, TRUE),
('OPENING',       'פתיחת עסק / Business Setup',                             'Initial business setup, permits, and registration', 100.00, TRUE),
('PHONE',         'פלאפון / Mobile Phone',                                  'Mobile phone and communication expenses', 66.00, TRUE),
('OFFICE_SUP',    'משרדיות ואחזקת משרד / Office Supplies & Maintenance',    'Office equipment, cleaning, small repairs, consumables', 100.00, TRUE)
ON CONFLICT (code) DO NOTHING;


