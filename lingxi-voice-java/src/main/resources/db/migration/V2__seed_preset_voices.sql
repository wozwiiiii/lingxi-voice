-- Seed preset voices (idempotent: uses ON CONFLICT DO NOTHING)
INSERT INTO voices (id, name, type, is_public, provider, provider_metadata, description)
VALUES
    ('a0000000-0000-0000-0000-000000000001', '温柔女声', 'preset', TRUE, 'cloud:siliconflow',
     '{"voice_id":"zh_female_wenrou"}', '温暖柔和的女声，适合教学讲解'),
    ('a0000000-0000-0000-0000-000000000002', '青涩男声', 'preset', TRUE, 'cloud:siliconflow',
     '{"voice_id":"zh_male_qingse"}', '年轻活力的男声'),
    ('a0000000-0000-0000-0000-000000000003', '男主播', 'preset', TRUE, 'cloud:siliconflow',
     '{"voice_id":"zh_male_zhubo"}', '专业播音风格男声'),
    ('a0000000-0000-0000-0000-000000000004', '女主播', 'preset', TRUE, 'cloud:siliconflow',
     '{"voice_id":"zh_female_zhubo"}', '专业播音风格女声'),
    ('a0000000-0000-0000-0000-000000000005', 'English Male', 'preset', TRUE, 'cloud:siliconflow',
     '{"voice_id":"en_male_narrator"}', 'Clear English male voice'),
    ('a0000000-0000-0000-0000-000000000006', 'English Female', 'preset', TRUE, 'cloud:siliconflow',
     '{"voice_id":"en_female_narrator"}', 'Clear English female voice')
ON CONFLICT (id) DO NOTHING;
