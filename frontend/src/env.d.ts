// Vue single-file component module shim for TypeScript.
// Provides a default-exported component shape so `import Foo from './Foo.vue'` compiles.
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
