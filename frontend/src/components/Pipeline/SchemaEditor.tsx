import React, { useState, useEffect } from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import Button from '../Common/Button';
import Input from '../Common/Input';

interface SchemaField {
  name: string;
  type: string;
  description: string;
}

const SchemaEditor: React.FC = () => {
  const { currentPipeline, updatePipeline } = usePipelineStore();
  const [fields, setFields] = useState<SchemaField[]>([]);
  const [newField, setNewField] = useState<SchemaField>({
    name: '',
    type: 'str',
    description: ''
  });

  useEffect(() => {
    // Convert schema object to fields array
    if (currentPipeline?.schema) {
      const schemaFields = Object.entries(currentPipeline.schema).map(([name, type]) => ({
        name,
        type: typeof type === 'string' ? type : 'str',
        description: ''
      }));
      setFields(schemaFields);
    }
  }, [currentPipeline?.schema]);

  const handleAddField = () => {
    if (!newField.name.trim() || !currentPipeline) return;

    const updatedFields = [...fields, newField];
    setFields(updatedFields);
    
    // Update pipeline schema
    const schema = updatedFields.reduce((acc, field) => ({
      ...acc,
      [field.name]: field.type
    }), {});
    
    updatePipeline(currentPipeline.id, { schema });
    
    // Reset form
    setNewField({ name: '', type: 'str', description: '' });
  };

  const handleRemoveField = (index: number) => {
    if (!currentPipeline) return;
    
    const updatedFields = fields.filter((_, i) => i !== index);
    setFields(updatedFields);
    
    // Update pipeline schema
    const schema = updatedFields.reduce((acc, field) => ({
      ...acc,
      [field.name]: field.type
    }), {});
    
    updatePipeline(currentPipeline.id, { schema });
  };

  const fieldTypes = [
    { value: 'str', label: 'String' },
    { value: 'int', label: 'Integer' },
    { value: 'float', label: 'Float' },
    { value: 'bool', label: 'Boolean' },
    { value: 'list', label: 'List' },
    { value: 'dict', label: 'Dictionary' }
  ];

  return (
    <div className="h-full flex flex-col p-4">
      <h3 className="text-lg font-semibold mb-4">Schema Definition</h3>
      
      {/* Add Field Form */}
      <div className="space-y-3 mb-4 card">
        <div className="grid grid-cols-3 gap-2">
          <Input
            value={newField.name}
            onChange={(e) => setNewField({ ...newField, name: e.target.value })}
            placeholder="Field name"
            disabled={!currentPipeline}
          />
          
          <select
            value={newField.type}
            onChange={(e) => setNewField({ ...newField, type: e.target.value })}
            className="input"
            disabled={!currentPipeline}
          >
            {fieldTypes.map(type => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
          
          <Button
            onClick={handleAddField}
            disabled={!newField.name.trim() || !currentPipeline}
            variant="primary"
          >
            Add Field
          </Button>
        </div>
        
        <Input
          value={newField.description}
          onChange={(e) => setNewField({ ...newField, description: e.target.value })}
          placeholder="Field description (optional)"
          disabled={!currentPipeline}
        />
      </div>
      
      {/* Fields List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {fields.length === 0 ? (
          <div className="text-center text-muted py-8">
            <p>No schema fields defined</p>
            <p className="text-sm mt-2">Add fields to define what data to extract</p>
          </div>
        ) : (
          fields.map((field, index) => (
            <div key={index} className="card flex items-center justify-between">
              <div>
                <div className="font-medium">{field.name}</div>
                <div className="text-sm text-muted">
                  Type: {fieldTypes.find(t => t.value === field.type)?.label || field.type}
                  {field.description && ` • ${field.description}`}
                </div>
              </div>
              
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleRemoveField(index)}
              >
                Remove
              </Button>
            </div>
          ))
        )}
      </div>
      
      {/* JSON Preview */}
      {fields.length > 0 && (
        <div className="mt-4 p-3 bg-code-bg rounded-md">
          <div className="text-xs text-muted mb-2">JSON Schema Preview:</div>
          <pre className="text-xs text-code-text">
            {JSON.stringify(
              fields.reduce((acc, field) => ({
                ...acc,
                [field.name]: field.type
              }), {}),
              null,
              2
            )}
          </pre>
        </div>
      )}
    </div>
  );
};

export default SchemaEditor;