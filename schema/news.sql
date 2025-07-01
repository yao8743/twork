-- Table: public.news_content

-- DROP TABLE IF EXISTS public.news_content;

CREATE TABLE IF NOT EXISTS public.news_content
(
    id integer NOT NULL DEFAULT nextval('news_content_id_seq'::regclass),
    title character varying COLLATE pg_catalog."default" NOT NULL,
    text text COLLATE pg_catalog."default",
    file_id character varying COLLATE pg_catalog."default",
    file_type character varying COLLATE pg_catalog."default",
    button_str text COLLATE pg_catalog."default",
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    bot_name character varying(30) COLLATE pg_catalog."default",
    business_type character varying(30) COLLATE pg_catalog."default",
    content_id bigint,
    CONSTRAINT news_content_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.news_content
    OWNER to neondb_owner;



-------

-- Table: public.news_send_queue

-- DROP TABLE IF EXISTS public.news_send_queue;

CREATE TABLE IF NOT EXISTS public.news_send_queue
(
    id integer NOT NULL DEFAULT nextval('news_send_queue_id_seq'::regclass),
    user_ref_id integer NOT NULL,
    news_id integer NOT NULL,
    bot_id integer,
    state send_state DEFAULT 'pending'::send_state,
    retry_count integer DEFAULT 0,
    last_try_at timestamp without time zone,
    sent_at timestamp without time zone,
    fail_reason text COLLATE pg_catalog."default",
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT news_send_queue_pkey PRIMARY KEY (id),
    CONSTRAINT news_send_queue_user_ref_id_news_id_key UNIQUE (user_ref_id, news_id),
    CONSTRAINT news_send_queue_news_id_fkey FOREIGN KEY (news_id)
        REFERENCES public.news_content (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT news_send_queue_user_ref_id_fkey FOREIGN KEY (user_ref_id)
        REFERENCES public.news_user (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.news_send_queue
    OWNER to neondb_owner;
-- Index: idx_send_queue_state

-- DROP INDEX IF EXISTS public.idx_send_queue_state;

CREATE INDEX IF NOT EXISTS idx_send_queue_state
    ON public.news_send_queue USING btree
    (state ASC NULLS LAST)
    TABLESPACE pg_default;
-- Index: idx_send_queue_state_bot

-- DROP INDEX IF EXISTS public.idx_send_queue_state_bot;

CREATE INDEX IF NOT EXISTS idx_send_queue_state_bot
    ON public.news_send_queue USING btree
    (state ASC NULLS LAST, bot_id ASC NULLS LAST)
    TABLESPACE pg_default;
-- Index: idx_send_queue_user_ref

-- DROP INDEX IF EXISTS public.idx_send_queue_user_ref;

CREATE INDEX IF NOT EXISTS idx_send_queue_user_ref
    ON public.news_send_queue USING btree
    (user_ref_id ASC NULLS LAST)
    TABLESPACE pg_default;

-------------
-- Table: public.news_user

-- DROP TABLE IF EXISTS public.news_user;

CREATE TABLE IF NOT EXISTS public.news_user
(
    id integer NOT NULL DEFAULT nextval('news_user_id_seq'::regclass),
    user_id bigint NOT NULL,
    business_type character varying(10) COLLATE pg_catalog."default" NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_sent_at timestamp without time zone,
    expire_at timestamp without time zone,
    CONSTRAINT news_user_pkey PRIMARY KEY (id),
    CONSTRAINT news_user_user_id_business_type_key UNIQUE (user_id, business_type)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.news_user
    OWNER to neondb_owner;