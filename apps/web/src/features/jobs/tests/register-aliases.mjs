import { register } from 'node:module';

register(new URL('./resolve-aliases.mjs', import.meta.url).href);
